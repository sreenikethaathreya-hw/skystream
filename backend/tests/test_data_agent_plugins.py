from dataclasses import dataclass, field

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from app.ai.data_agent.number_guard import REDACTED
from app.ai.data_agent.plugins import NumberGuardPlugin, ScopeGuardPlugin
from app.ai.data_agent.policy import POLICY_KEY, ChatPolicy


@dataclass
class FakeTool:
    name: str


@dataclass
class FakeContext:
    state: dict = field(default_factory=dict)
    user_content: types.Content | None = None
    invocation_id: str = "e-test"


def _state(role: str = "rep", visible: tuple[int, ...] = (2482,)) -> dict:
    policy = ChatPolicy(
        user_id="u", user_name="U", role=role, country_code="ES", mega_segment_id="SP01",
        visible_segment_ids=list(visible), is_demo=False,
    )
    return {POLICY_KEY: policy.model_dump()}


def _text(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


async def test_scope_guard_blocks_hidden_segments_and_lead_tools() -> None:
    guard = ScopeGuardPlugin()
    ctx = FakeContext(state=_state())
    assert await guard.before_tool_callback(tool=FakeTool("get_monthly_series"), tool_args={"segment_id": 2482},
                                            tool_context=ctx) is None
    blocked = await guard.before_tool_callback(tool=FakeTool("get_monthly_series"), tool_args={"segment_id": 2432},
                                               tool_context=ctx)
    assert blocked["status"] == "error"
    blocked = await guard.before_tool_callback(
        tool=FakeTool("sum_segment_figures"), tool_args={"segment_ids": [2482, 2432]}, tool_context=ctx
    )
    assert blocked["status"] == "error"
    blocked = await guard.before_tool_callback(tool=FakeTool("list_open_exceptions"), tool_args={}, tool_context=ctx)
    assert blocked["status"] == "error"
    lead = FakeContext(state=_state("lead"))
    assert await guard.before_tool_callback(tool=FakeTool("list_open_exceptions"), tool_args={},
                                            tool_context=lead) is None


async def test_scope_guard_requires_a_policy() -> None:
    blocked = await ScopeGuardPlugin().before_tool_callback(
        tool=FakeTool("list_segments"), tool_args={}, tool_context=FakeContext()
    )
    assert blocked["status"] == "error"


async def test_number_guard_keeps_quoted_and_redacts_invented() -> None:
    guard = NumberGuardPlugin()
    ctx = FakeContext(
        state=_state(), user_content=types.Content(role="user", parts=[types.Part(text="share of 2482 in 2026?")])
    )
    await guard.after_tool_callback(tool=FakeTool("x"), tool_args={}, tool_context=ctx,
                                    result={"status": "success", "share": 20.2})
    assert await guard.after_model_callback(callback_context=ctx, llm_response=_text("2482 is at 20.2% in 2026.")) is None
    replaced = await guard.after_model_callback(callback_context=ctx, llm_response=_text("It is 20.2%, plan 31.5%."))
    assert replaced.content.parts[0].text == f"It is 20.2%, plan {REDACTED}%."
    assert replaced.custom_metadata["numbers_redacted"] is True


async def test_number_guard_ignores_function_calls() -> None:
    call = LlmResponse(
        content=types.Content(
            role="model", parts=[types.Part(function_call=types.FunctionCall(name="x", args={"segment_id": 999}))]
        )
    )
    assert await NumberGuardPlugin().after_model_callback(callback_context=FakeContext(), llm_response=call) is None
