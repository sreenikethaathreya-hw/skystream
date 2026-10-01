"""Runner-level guardrails for the data chat. Each plugin does one job and never lets its own error escape."""

import logging
import time
from typing import Any

from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

from app.ai.data_agent.number_guard import collect_numbers, find_unverified, redact
from app.ai.data_agent.policy import (
    ADMIN_ONLY_TOOLS,
    ALLOWED_NUMBERS_KEY,
    LEAD_ONLY_TOOLS,
    LEAD_WRITE_TOOLS,
    MAX_WRITES_PER_TURN,
    REP_WRITE_TOOLS,
    USER_NUMBER_ARGS,
    USER_NUMBER_TOOLS,
    VERBATIM_TEXT_ARGS,
    WRITE_TOOLS,
    WRITES_KEY,
    read_policy,
)
from app.database import async_session
from app.models import ChatAction

logger = logging.getLogger(__name__)

SCOPE_ERROR = {"status": "error", "error_message": "That is not in your scope."}
QUOTES = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"})


def _text_of(content: types.Content | None) -> str:
    return "".join(p.text or "" for p in (content.parts if content else None) or [] if not p.thought)


def _normal(text: str) -> str:
    return " ".join(text.translate(QUOTES).casefold().split())


def quotes_user(argument: str, user_text: str) -> bool:
    """True when the argument is a contiguous quote of what the user wrote (case and spacing aside)."""
    quoted = _normal(argument).strip("\"' ").rstrip(".")
    return not quoted or quoted in _normal(user_text)


def typed_by_user(value: float, user_numbers: list[float]) -> bool:
    return any(abs(value - n) < 1e-6 for n in user_numbers)


def _blocked(message: str) -> dict:
    return {"status": "error", "error_message": message, "blocked": True}


class ScopeGuardPlugin(BasePlugin):
    """Blocks a tool call before it runs when the model asks for a segment or tool outside the caller's policy."""

    def __init__(self) -> None:
        super().__init__(name="scope_guard")

    async def before_tool_callback(self, *, tool, tool_args: dict[str, Any], tool_context) -> dict | None:
        try:
            policy = read_policy(tool_context.state)
            if policy is None:
                return {"status": "error", "error_message": "No access policy was set for this conversation."}
            if tool.name in LEAD_ONLY_TOOLS and not policy.is_lead:
                return SCOPE_ERROR
            if tool.name in ADMIN_ONLY_TOOLS and not policy.is_admin:
                return SCOPE_ERROR
            requested = [tool_args.get("segment_id") or 0, *(tool_args.get("segment_ids") or [])]
            if any(int(s) and not policy.can_see(int(s)) for s in requested):
                return SCOPE_ERROR
        except (TypeError, ValueError):
            return {"status": "error", "error_message": "segment ids must be whole numbers"}
        except Exception:
            logger.exception("Scope guard failed; blocking the tool call")
            return SCOPE_ERROR
        return None


class WriteGuardPlugin(BasePlugin):
    """Holds every change the agent makes to the user's own words and numbers, and to who may make it.

    Write tools need the chatWritesAllowed setting, the right role and fewer than MAX_WRITES_PER_TURN successful
    writes this turn. For any tool, numeric inputs listed in USER_NUMBER_ARGS must appear in the user's message
    and text inputs in VERBATIM_TEXT_ARGS must quote it, so the model never authors a number or a claim.
    """

    def __init__(self) -> None:
        super().__init__(name="write_guard")

    async def before_tool_callback(self, *, tool, tool_args: dict[str, Any], tool_context) -> dict | None:
        try:
            user_text = _text_of(tool_context.user_content)
            for key in VERBATIM_TEXT_ARGS:
                value = tool_args.get(key)
                if isinstance(value, str) and not quotes_user(value, user_text):
                    return _blocked(
                        f"The {key.replace('_', ' ')} must be the user's own words from this message. Ask the "
                        "user to write it; do not write or rephrase it for them."
                    )
            if tool.name in USER_NUMBER_TOOLS:
                typed = collect_numbers(user_text)
                for key in USER_NUMBER_ARGS:
                    value = tool_args.get(key)
                    if isinstance(value, int | float) and value and not typed_by_user(float(value), typed):
                        return _blocked(
                            f"The {key} must be a number the user typed in this message. Ask the user for it; "
                            "never choose, round or work out a number for them."
                        )
            if tool.name not in WRITE_TOOLS:
                return None
            policy = read_policy(tool_context.state)
            if policy is None:
                return _blocked("No access policy was set for this conversation.")
            if not policy.writes_allowed:
                return _blocked("Changes through the chat are turned off. Use the page instead.")
            if tool.name in REP_WRITE_TOOLS and policy.role != "rep":
                return _blocked("Only reps can do that.")
            if tool.name in LEAD_WRITE_TOOLS and not policy.is_lead:
                return _blocked("Only consensus leads and admins can do that.")
            if int(tool_context.state.get(WRITES_KEY) or 0) >= MAX_WRITES_PER_TURN:
                return _blocked("Only one change per message. Ask the user to confirm the next change separately.")
        except Exception:
            logger.exception("Write guard failed; blocking the tool call")
            return _blocked("The change could not be checked, so it was not made.")
        return None

    async def after_tool_callback(self, *, tool, tool_args, tool_context, result) -> dict | None:
        try:
            if tool.name in WRITE_TOOLS and isinstance(result, dict) and result.get("action"):
                tool_context.state[WRITES_KEY] = int(tool_context.state.get(WRITES_KEY) or 0) + 1
        except Exception:
            logger.exception("Write guard could not count the write")
        return None


class NumberGuardPlugin(BasePlugin):
    """Collects every number tools return this turn and removes numbers from the answer that are not among them."""

    def __init__(self) -> None:
        super().__init__(name="number_guard")

    async def after_tool_callback(self, *, tool, tool_args, tool_context, result) -> dict | None:
        try:
            allowed = list(tool_context.state.get(ALLOWED_NUMBERS_KEY) or [])
            tool_context.state[ALLOWED_NUMBERS_KEY] = allowed + collect_numbers(result)
        except Exception:
            logger.exception("Number guard could not record tool numbers")
        return None

    async def after_model_callback(self, *, callback_context, llm_response: LlmResponse) -> LlmResponse | None:
        try:
            content = llm_response.content
            if llm_response.partial or content is None:
                return None
            if any(p.function_call for p in content.parts or []):
                return None
            text = _text_of(content)
            if not text:
                return None
            allowed = list(callback_context.state.get(ALLOWED_NUMBERS_KEY) or [])
            allowed += collect_numbers(_text_of(callback_context.user_content))
            unverified = find_unverified(text, allowed)
            if not unverified:
                return None
            logger.info("Number guard removed %d unverified numbers", len(unverified))
            return LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text=redact(text, unverified))]),
                custom_metadata={**(llm_response.custom_metadata or {}), "numbers_redacted": True},
                usage_metadata=llm_response.usage_metadata,
            )
        except Exception:
            logger.exception("Number guard failed; withholding the answer")
            return LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text="I could not check that answer. Please see the tables.")]
                ),
                custom_metadata={"numbers_redacted": True},
            )


def _audit_args(tool_args: dict) -> dict:
    return {k: v[:600] if isinstance(v, str) else v for k, v in tool_args.items()}


async def record_action(user_id: str, session_id: str, invocation_id: str, tool: str, args: dict, result) -> None:
    result = result if isinstance(result, dict) else {}
    action = result.get("action") or {}
    status = "success" if action else ("blocked" if result.get("blocked") else "error")
    async with async_session() as db:
        db.add(
            ChatAction(
                user_id=user_id,
                session_id=session_id,
                invocation_id=invocation_id,
                tool=tool,
                target_type=action.get("target_type"),
                target_id=action.get("target_id") or args.get("entry_id") or None,
                args=_audit_args(args),
                status=status,
                detail=action.get("summary") or result.get("error_message"),
            )
        )
        await db.commit()


class AuditPlugin(BasePlugin):
    """Logs who asked, which tools ran and how long the turn took, and stores every write attempt in chat_actions.

    The log line never carries questions, answers or figures; chat_actions keeps the write's arguments so a lead
    can see what the assistant changed.
    """

    def __init__(self) -> None:
        super().__init__(name="audit")
        self._runs: dict[str, tuple[float, list[str]]] = {}

    async def before_run_callback(self, *, invocation_context) -> None:
        self._runs[invocation_context.invocation_id] = (time.perf_counter(), [])
        return None

    async def after_tool_callback(self, *, tool, tool_args, tool_context, result) -> None:
        run = self._runs.get(tool_context.invocation_id)
        if run is not None:
            run[1].append(f"{tool.name}:{result.get('status', '?') if isinstance(result, dict) else '?'}")
        if tool.name in WRITE_TOOLS:
            try:
                policy = read_policy(tool_context.state)
                await record_action(
                    policy.user_id if policy else tool_context.user_id,
                    tool_context.session.id,
                    tool_context.invocation_id,
                    tool.name,
                    dict(tool_args or {}),
                    result,
                )
            except Exception:
                logger.exception("Could not record the chat action")
        return None

    async def after_run_callback(self, *, invocation_context) -> None:
        started, tools = self._runs.pop(invocation_context.invocation_id, (time.perf_counter(), []))
        logger.info(
            "Data chat turn user=%s invocation=%s tools=%s latency_ms=%.0f",
            invocation_context.session.user_id,
            invocation_context.invocation_id,
            ",".join(tools) or "none",
            (time.perf_counter() - started) * 1000,
        )
        return None
