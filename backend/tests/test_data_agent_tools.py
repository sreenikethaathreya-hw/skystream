from app.ai.data_agent import tools
from app.ai.data_agent.policy import POLICY_KEY, ChatPolicy
from app.ai.offline_chat import ToolState
from app.database import async_session
from app.schemas.demand_math import EntryInput
from app.services.context_service import build_context
from app.services.demand_math import compute_impact

ALL_SEGMENTS = [2432, 2433, 2446, 2448, 2449, 2481, 2482, 2483, 2484]


def _ctx(role: str = "rep", visible: list[int] | None = None) -> ToolState:
    policy = ChatPolicy(
        user_id="rep-a" if role == "rep" else role,
        user_name="Rep A" if role == "rep" else role,
        role=role,
        country_code="ES",
        mega_segment_id="SP01",
        visible_segment_ids=ALL_SEGMENTS if visible is None else visible,
        is_demo=True,
    )
    return ToolState(state={POLICY_KEY: policy.model_dump()})


async def test_every_tool_reports_a_status(seeded: None) -> None:
    ctx = _ctx("lead")
    results = [
        await tools.list_segments(ctx),
        await tools.get_segment_baseline(2482, 10, ctx),
        await tools.get_monthly_series(2482, ctx),
        await tools.list_demand_entries(0, 0, "", "", ctx),
        await tools.get_competitor_shares(ctx),
        await tools.get_rep_track_records("", ctx),
        await tools.list_lead_rules(ctx),
        await tools.list_open_exceptions(ctx),
        await tools.sum_segment_figures("plan_ks", [2482, 2484], [10, 11], ctx),
        await tools.get_ibp_forecast(2482, ctx),
    ]
    assert all(r["status"] == "success" for r in results), [r for r in results if r["status"] != "success"]


async def test_ibp_forecast_tool_shows_varieties_and_reference_status(seeded: None) -> None:
    result = await tools.get_ibp_forecast(2432, _ctx())
    october = [r for r in result["rows"] if r[0] == "Oct"]
    assert {r[1] for r in october} == {"Bokken", "Kaamos"}
    assert result["month_totals_ks"]["Oct"] == 7090
    assert all(r[4] == "reference only" for r in result["rows"])


async def test_out_of_scope_segment_is_refused_without_figures(seeded: None) -> None:
    ctx = _ctx(visible=[2482])
    for result in (
        await tools.get_ibp_forecast(2432, ctx),
        await tools.get_segment_baseline(2432, 10, ctx),
        await tools.get_monthly_series(2432, ctx),
        await tools.list_demand_entries(2432, 0, "", "", ctx),
        await tools.sum_segment_figures("plan_ks", [2432], [], ctx),
    ):
        assert result["status"] == "error"
        assert "rows" not in result and "figures" not in result


async def test_open_exceptions_are_lead_only(seeded: None) -> None:
    result = await tools.list_open_exceptions(_ctx("rep"))
    assert result["status"] == "error"


async def test_missing_policy_is_an_error(seeded: None) -> None:
    assert (await tools.list_segments(ToolState()))["status"] == "error"


async def test_baseline_matches_the_capture_math(seeded: None) -> None:
    result = await tools.get_segment_baseline(2482, 10, _ctx())
    async with async_session() as db:
        ctx, _, _ = await build_context(db, "ES", 2482)
    baseline = ctx.submitted.get("10", ctx.monthly_plan[9])
    impact = compute_impact(ctx, EntryInput(month=10, value=baseline, low=baseline, high=baseline))
    figures = result["figures"]
    assert figures["share_now_pct"] == round(impact.volume_share * 100, 1)
    assert figures["year_to_go_ks"] == round(impact.ytg_remaining)
    assert figures["month_plan_ks"] == round(ctx.monthly_plan[9])


async def test_sum_is_computed_on_the_server(seeded: None) -> None:
    ctx = _ctx()
    result = await tools.sum_segment_figures("plan_ks", [2482, 2484], [10], ctx)
    one = await tools.get_segment_baseline(2482, 10, ctx)
    two = await tools.get_segment_baseline(2484, 10, ctx)
    expected = one["figures"]["month_plan_ks"] + two["figures"]["month_plan_ks"]
    assert abs(result["total_ks"] - expected) <= 1
    assert (await tools.sum_segment_figures("revenue", [], [], ctx))["status"] == "error"
