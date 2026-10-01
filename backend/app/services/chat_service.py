"""Chat sessions and turns for "Ask the data". Every session lookup is keyed by the caller's own user id."""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.data_agent.history import to_messages, turn_parts
from app.ai.data_agent.policy import ChatPolicy, PageContext, policy_for
from app.ai.data_agent.runtime import DataAgentRuntime, get_runtime
from app.ai.decision_provider import DecisionPolicy, decision_policy, get_decision_provider
from app.config import get_settings
from app.schemas.chat import (
    ChatActionOut,
    ChatDownloadOut,
    ChatHistoryOut,
    ChatLinkOut,
    ChatMessageIn,
    ChatMessageOut,
    ChatSessionOut,
    ChatSourceOut,
    ChatTurnOut,
)
from app.services.context_service import resolve_scope, visible_segments
from app.services.settings_service import get_app_settings
from app.services.user_service import CurrentUser

logger = logging.getLogger(__name__)

TITLE_KEY = "title"
TITLE_LENGTH = 60
NEW_TITLE = "New conversation"
# Per-process turn timestamps for the per-user rate limit; Cloud Run instances each keep their own.
_turns: dict[str, deque[float]] = defaultdict(deque)


def _runtime() -> DataAgentRuntime:
    runtime = get_runtime()
    if runtime is None or not get_settings().chat_enabled:
        raise HTTPException(status_code=503, detail="Ask the data is not enabled")
    return runtime


def _session_out(session) -> ChatSessionOut:
    return ChatSessionOut(
        id=session.id,
        title=(session.state or {}).get(TITLE_KEY) or NEW_TITLE,
        updated_at=datetime.fromtimestamp(session.last_update_time, tz=UTC),
    )


async def _own_session(runtime: DataAgentRuntime, user: CurrentUser, session_id: str):
    session = await runtime.sessions.get_session(app_name=runtime.app_name, user_id=user.id, session_id=session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return session


async def create_session(user: CurrentUser) -> ChatSessionOut:
    runtime = _runtime()
    session = await runtime.sessions.create_session(app_name=runtime.app_name, user_id=user.id, state={TITLE_KEY: ""})
    return _session_out(session)


async def list_sessions(user: CurrentUser) -> list[ChatSessionOut]:
    runtime = _runtime()
    listed = await runtime.sessions.list_sessions(app_name=runtime.app_name, user_id=user.id)
    return [_session_out(s) for s in reversed(listed.sessions)]


async def get_history(user: CurrentUser, session_id: str) -> ChatHistoryOut:
    runtime = _runtime()
    session = await _own_session(runtime, user, session_id)
    return ChatHistoryOut(
        session=_session_out(session),
        messages=[ChatMessageOut.model_validate(m, from_attributes=True) for m in to_messages(session)],
    )


async def delete_session(user: CurrentUser, session_id: str) -> None:
    runtime = _runtime()
    await _own_session(runtime, user, session_id)
    await runtime.sessions.delete_session(app_name=runtime.app_name, user_id=user.id, session_id=session_id)


async def delete_all_sessions() -> int:
    """Demo reset only: drops every conversation for every user."""
    runtime = get_runtime()
    if runtime is None:
        return 0
    listed = await runtime.sessions.list_sessions(app_name=runtime.app_name)
    for s in listed.sessions:
        await runtime.sessions.delete_session(app_name=runtime.app_name, user_id=s.user_id, session_id=s.id)
    return len(listed.sessions)


@dataclass
class PreparedTurn:
    session_id: str
    text: str
    chat_policy: ChatPolicy
    policy: DecisionPolicy
    state_delta: dict
    page_context: PageContext | None


def _check_rate(user: CurrentUser) -> None:
    limit = get_settings().chat_turns_per_minute
    now = time.monotonic()
    recent = _turns[user.id]
    while recent and now - recent[0] > 60:
        recent.popleft()
    if limit and len(recent) >= limit:
        raise HTTPException(status_code=429, detail="Too many questions in a minute; wait a moment and ask again")
    recent.append(now)


def _page_context(body: ChatMessageIn, visible: set[int]) -> PageContext | None:
    """Keeps only the ids the caller may see, so the page context can never widen the policy."""
    if body.page_context is None:
        return None
    raw = body.page_context
    return PageContext(
        page=raw.page,
        segment_id=raw.segment_id if raw.segment_id in visible else None,
        month=raw.month,
        entry_id=raw.entry_id,
        rule_id=raw.rule_id,
    )


async def prepare_turn(db: AsyncSession, user: CurrentUser, session_id: str, body: ChatMessageIn) -> PreparedTurn:
    runtime = _runtime()
    session = await _own_session(runtime, user, session_id)
    _check_rate(user)
    country, mega = await resolve_scope(db, user, body.country_code, body.mega_segment_id)
    segment_ids = [s.id for s in await visible_segments(db, user, country, mega)]
    app_settings = await get_app_settings(db)
    chat_policy = policy_for(
        user,
        country,
        mega,
        segment_ids,
        get_settings().is_demo,
        writes_allowed=app_settings.chat_writes_allowed,
        demand_source=app_settings.demand_source,
    )
    policy = decision_policy(app_settings)
    # Release the request's read transaction so ADK and the tools can write and read on their own connections.
    await db.rollback()
    text = body.text.strip()
    state_delta = {} if (session.state or {}).get(TITLE_KEY) else {TITLE_KEY: text[:TITLE_LENGTH]}
    return PreparedTurn(
        session_id, text, chat_policy, policy, state_delta, _page_context(body, set(segment_ids))
    )


async def run_turn(
    user: CurrentUser, turn: PreparedTurn, on_event: Callable[[str, dict], Awaitable[None]] | None = None
) -> ChatTurnOut:
    started = time.perf_counter()
    answer = await get_decision_provider().answer_data_question(
        turn.session_id,
        turn.text,
        turn.chat_policy,
        turn.policy,
        turn.state_delta,
        on_event=on_event,
        page_context=turn.page_context,
    )
    parts = turn_parts(answer.results)
    logger.info(
        "Chat turn user=%s intent=%s provider=%s tools=%s redacted=%s actions=%d latency_ms=%.0f",
        user.id,
        answer.intent,
        answer.provider,
        ",".join(name for name, _ in answer.results) or "none",
        answer.numbers_redacted,
        len(parts.actions),
        (time.perf_counter() - started) * 1000,
    )
    return ChatTurnOut(
        session_id=turn.session_id,
        answer=answer.text,
        intent=answer.intent,
        provider=answer.provider,
        numbers_redacted=answer.numbers_redacted,
        sources=[ChatSourceOut.model_validate(s, from_attributes=True) for s in parts.sources],
        links=[ChatLinkOut.model_validate(link, from_attributes=True) for link in parts.links],
        actions=[ChatActionOut.model_validate(a, from_attributes=True) for a in parts.actions],
        downloads=[ChatDownloadOut.model_validate(d, from_attributes=True) for d in parts.downloads],
    )


async def send_message(db: AsyncSession, user: CurrentUser, session_id: str, body: ChatMessageIn) -> ChatTurnOut:
    return await run_turn(user, await prepare_turn(db, user, session_id, body))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def stream_turn(user: CurrentUser, turn: PreparedTurn) -> AsyncIterator[str]:
    """Server-sent events: tool progress while the agent works, then one `final` event with the checked turn."""
    queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

    async def on_event(kind: str, data: dict) -> None:
        await queue.put((kind, data))

    async def work() -> ChatTurnOut:
        try:
            return await run_turn(user, turn, on_event)
        finally:
            await queue.put(None)

    task = asyncio.create_task(work())
    while (item := await queue.get()) is not None:
        yield _sse(*item)
    try:
        out = await task
    except HTTPException as exc:
        yield _sse("error", {"detail": exc.detail})
        return
    except Exception:
        logger.exception("Streamed chat turn failed")
        yield _sse("error", {"detail": "The question could not be answered"})
        return
    yield _sse("final", out.model_dump(mode="json", by_alias=True))
