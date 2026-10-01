from types import SimpleNamespace as NS

from httpx import AsyncClient

from app.services.cube_builder import Reference, build_mega, build_segment_context, last_year_basis

REP_A = {"X-Demo-User": "rep-a"}


def _ref(with_monthly_actuals: bool) -> Reference:
    seg = NS(id=1, mega_segment_desc="M")
    market = [NS(segment_id=1, year=y, hectares=100.0, qty_ks=1000.0, density=10.0, price_exseed=1.0, notes={})
              for y in (2024, 2025, 2026, 2027)]
    plan = [NS(segment_id=1, year=y, qty_ks=q, value_usd=q * 2, net_price=2.0)
            for y, q in ((2024, 300.0), (2025, 320.0), (2026, 340.0), (2027, 360.0))]
    monthly_plan = [NS(segment_id=1, year=y, month=m, qty_ks=p.qty_ks / 12)
                    for y, p in ((p.year, p) for p in plan) for m in range(1, 13)]
    actuals = (
        [NS(segment_id=1, year=2025, month=m, qty_ks=25.0, value_usd=50.0) for m in range(1, 13)]
        if with_monthly_actuals
        else []
    )
    return Reference(segments=[seg], market=market, plan=plan, monthly_plan=monthly_plan, monthly_actuals=actuals)


def test_rows_before_the_planning_year_are_actual_sales() -> None:
    ref = _ref(with_monthly_actuals=False)
    ctx = build_segment_context(ref, 1, 2026, 1, {}, build_mega(ref, 2026))
    assert [(p.year, p.basis) for p in ctx.plan_qty_history] == [(2024, "actual"), (2025, "actual"), (2026, "plan")]
    assert last_year_basis(ref, 1, 2026) == "annual_actuals"
    assert ctx.last_year_qty_ks == 320.0
    assert {h.year: h.basis for h in ctx.monthly_history} == {2024: "annual_actuals", 2025: "annual_actuals"}


def test_full_monthly_actuals_win_over_the_annual_figure() -> None:
    ref = _ref(with_monthly_actuals=True)
    assert last_year_basis(ref, 1, 2026) == "actuals"
    ctx = build_segment_context(ref, 1, 2026, 1, {}, build_mega(ref, 2026))
    assert ctx.last_year_qty_ks == 300.0


def test_rollover_turns_last_plan_year_into_actuals() -> None:
    ref = _ref(with_monthly_actuals=False)
    ctx = build_segment_context(ref, 1, 2027, 1, {}, build_mega(ref, 2027))
    assert dict((p.year, p.basis) for p in ctx.plan_qty_history)[2026] == "actual"
    assert dict((p.year, p.basis) for p in ctx.plan_qty_history)[2027] == "plan"


async def test_cube_and_chat_label_the_basis(client: AsyncClient) -> None:
    cube = (await client.get("/api/segments/cube", headers=REP_A)).json()
    seg = next(s for s in cube["segments"] if s["id"] == 2482)
    bases = {p["year"]: p["basis"] for p in seg["context"]["planQtyHistory"]}
    assert bases[cube["year"]] == "plan"
    assert all(b == "actual" for y, b in bases.items() if y < cube["year"])
