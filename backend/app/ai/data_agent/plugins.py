"""Runner-level guardrails for the data chat. Each plugin does one job and never lets its own error escape."""

import logging
import time
from typing import Any

from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

from app.ai.data_agent.number_guard import collect_numbers, find_unverified, redact
from app.ai.data_agent.policy import ALLOWED_NUMBERS_KEY, LEAD_ONLY_TOOLS, read_policy

logger = logging.getLogger(__name__)

SCOPE_ERROR = {"status": "error", "error_message": "That is not in your scope."}


def _text_of(content: types.Content | None) -> str:
    return "".join(p.text or "" for p in (content.parts if content else None) or [] if not p.thought)


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
            requested = [tool_args.get("segment_id") or 0, *(tool_args.get("segment_ids") or [])]
            if any(int(s) and not policy.can_see(int(s)) for s in requested):
                return SCOPE_ERROR
        except (TypeError, ValueError):
            return {"status": "error", "error_message": "segment ids must be whole numbers"}
        except Exception:
            logger.exception("Scope guard failed; blocking the tool call")
            return SCOPE_ERROR
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


class AuditPlugin(BasePlugin):
    """Logs who asked, which tools ran and how long the turn took. Never logs questions, answers or figures."""

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
