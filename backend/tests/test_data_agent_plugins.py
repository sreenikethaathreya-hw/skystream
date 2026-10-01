from dataclasses import dataclass, field

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from app.ai.data_agent.number_guard import REDACTED
from app.ai.data_agent.plugins import NumberGuardPlugin, ScopeGuardPlugin, WriteGuardPlugin, quotes_user
from app.ai.data_agent.policy import POLICY_KEY, WRITES_KEY, ChatPolicy


@dataclass
class FakeTool:
    name: str


@dataclass
class FakeContext:
    state: dict = field(default_factory=dict)
    user_content: types.Content | None = None
    invocation_id: str = "e-test"


def _state(role: str = "rep", visible: tuple[int, ...] = (2482,), writes: bool = True) -> dict:
    policy = ChatPolicy(
        user_id="u", user_name="U", role=role, country_code="ES", mega_segment_id="SP01",
        visible_segment_ids=list(visible), is_demo=False, writes_allowed=writes,
    )
    return {POLICY_KEY: policy.model_dump()}


def _said(text: str, role: str = "rep", writes: bool = True) -> FakeContext:
    return FakeContext(
        state=_state(role, writes=writes), user_content=types.Content(role="user", parts=[types.Part(text=text)])
    )


SAID = "Please enter 4,000 KS for 2482 October, range 3800 to 4200, because Corteva dropped its blocky variety."
SUBMIT = {
    "segment_id": 2482, "month": 10, "value": 4000, "low": 3800, "high": 4200, "price": 0,
    "justification": "Corteva dropped its blocky variety",
}


async def _guard(tool: str, args: dict, ctx: FakeContext) -> dict | None:
    return await WriteGuardPlugin().before_tool_callback(tool=FakeTool(tool), tool_args=args, tool_context=ctx)


async def test_write_guard_allows_the_users_own_numbers_and_words() -> None:
    assert await _guard("submit_demand_entry", SUBMIT, _said(SAID)) is None


async def test_write_guard_blocks_a_number_the_user_did_not_type() -> None:
    for key, value in (("value", 4100), ("low", 3600), ("high", 4400)):
        blocked = await _guard("submit_demand_entry", {**SUBMIT, key: value}, _said(SAID))
        assert blocked["blocked"] is True and key in blocked["error_message"]
    blocked = await _guard("preview_entry_impact", {**SUBMIT, "value": 4100}, _said(SAID))
    assert blocked["status"] == "error"


async def test_write_guard_blocks_a_justification_the_model_wrote() -> None:
    reworded = {**SUBMIT, "justification": "A competitor exited the segment, freeing share"}
    blocked = await _guard("submit_demand_entry", reworded, _said(SAID))
    assert blocked["blocked"] is True and "own words" in blocked["error_message"]
    note = await _guard("add_entry_note", {"entry_id": "x", "note": "Approved by the lead"}, _said("add a note"))
    assert note["status"] == "error"


async def test_write_guard_enforces_role_setting_and_one_write_per_turn() -> None:
    assert (await _guard("decide_entry", {"decision": "approve"}, _said("approve it")))["blocked"]
    assert await _guard("decide_entry", {"decision": "approve"}, _said("approve it", role="lead")) is None
    assert (await _guard("submit_demand_entry", {}, _said("submit", role="lead")))["blocked"]
    off = await _guard("submit_demand_entry", SUBMIT, _said(SAID, writes=False))
    assert "turned off" in off["error_message"]

    ctx = _said(SAID)
    guard = WriteGuardPlugin()
    await guard.after_tool_callback(tool=FakeTool("submit_demand_entry"), tool_args=SUBMIT, tool_context=ctx,
                                    result={"status": "success", "action": {"kind": "entry_submitted"}})
    assert ctx.state[WRITES_KEY] == 1
    second = await guard.before_tool_callback(tool=FakeTool("submit_demand_entry"), tool_args=SUBMIT, tool_context=ctx)
    assert "one change" in second["error_message"].lower()


def test_quotes_user_ignores_case_spacing_and_smart_quotes() -> None:
    assert quotes_user("corteva  DROPPED its blocky variety.", "Because \u201cCorteva dropped its blocky variety\u201d")
    assert quotes_user("", "anything")
    assert not quotes_user("Corteva left", "Corteva dropped")


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
    for lead_tool in ("rank_segments", "compile_lead_rule", "get_upload_status"):
        blocked = await guard.before_tool_callback(tool=FakeTool(lead_tool), tool_args={}, tool_context=ctx)
        assert blocked["status"] == "error"
    lead = FakeContext(state=_state("lead"))
    blocked = await guard.before_tool_callback(tool=FakeTool("get_upload_status"), tool_args={}, tool_context=lead)
    assert blocked["status"] == "error"
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
