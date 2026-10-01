"""Chat sessions and turns for "Ask the data". Every session lookup is keyed by the caller's own user id."""

import logging
import time
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.data_agent.history import sources_and_links, to_messages
from app.ai.data_agent.policy import policy_for
from app.ai.data_agent.runtime import DataAgentRuntime, get_runtime
from app.ai.decision_provider import decision_policy, get_decision_provider
from app.config import get_settings
from app.schemas.chat import (
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


async def send_message(db: AsyncSession, user: CurrentUser, session_id: str, body: ChatMessageIn) -> ChatTurnOut:
    runtime = _runtime()
    session = await _own_session(runtime, user, session_id)
    country, mega = await resolve_scope(db, user, body.country_code, body.mega_segment_id)
    segments = await visible_segments(db, user, country, mega)
    chat_policy = policy_for(user, country, mega, [s.id for s in segments], get_settings().is_demo)
    policy = decision_policy(await get_app_settings(db))
    # Release the request's read transaction so ADK and the tools can write and read on their own connections.
    await db.rollback()

    text = body.text.strip()
    state_delta = {} if (session.state or {}).get(TITLE_KEY) else {TITLE_KEY: text[:TITLE_LENGTH]}
    started = time.perf_counter()
    answer = await get_decision_provider().answer_data_question(session_id, text, chat_policy, policy, state_delta)
    sources, links = sources_and_links(answer.results)
    logger.info(
        "Chat turn user=%s intent=%s provider=%s tools=%s redacted=%s latency_ms=%.0f",
        user.id,
        answer.intent,
        answer.provider,
        ",".join(name for name, _ in answer.results) or "none",
        answer.numbers_redacted,
        (time.perf_counter() - started) * 1000,
    )
    return ChatTurnOut(
        session_id=session_id,
        answer=answer.text,
        intent=answer.intent,
        provider=answer.provider,
        numbers_redacted=answer.numbers_redacted,
        sources=[ChatSourceOut.model_validate(s, from_attributes=True) for s in sources],
        links=[ChatLinkOut.model_validate(link, from_attributes=True) for link in links],
    )
