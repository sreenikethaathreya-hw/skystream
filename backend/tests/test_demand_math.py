import json
import math
from pathlib import Path

import pytest

from app.schemas.demand_math import EntryInput, SegmentContext
from app.services.demand_math import compute_impact
from app.services.flags import evaluate_flags

CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "demand_math_cases.json").read_text()
)


def _assert_close(actual, expected, path: str) -> None:
    if isinstance(expected, float | int) and not isinstance(expected, bool):
        assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9), path
    elif isinstance(expected, list):
        assert len(actual) == len(expected), path
        for i, (a, e) in enumerate(zip(actual, expected)):
            _assert_close(a, e, f"{path}[{i}]")
    elif isinstance(expected, dict):
        for key, value in expected.items():
            _assert_close(actual[key], value, f"{path}.{key}")
    else:
        assert actual == expected, path


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden_case(case: dict) -> None:
    ctx = SegmentContext.model_validate(case["context"])
    entry = EntryInput.model_validate(case["entry"])
    impact = compute_impact(ctx, entry)
    _assert_close(impact.model_dump(by_alias=True), case["expected"], "impact")
    assert [f.code for f in evaluate_flags(ctx, entry, impact)] == case["expectedFlags"]


def _ctx() -> SegmentContext:
    return SegmentContext.model_validate(CASES[0]["context"])


def test_share_is_linear_in_the_entered_number() -> None:
    ctx = _ctx()
    base = compute_impact(ctx, EntryInput(month=9, value=10000, low=9000, high=11000))
    raised = compute_impact(ctx, EntryInput(month=9, value=11000, low=10000, high=12000))
    assert raised.fy_estimate - base.fy_estimate == pytest.approx(1000)
    assert raised.volume_share - base.volume_share == pytest.approx(1000 / ctx.market_qty_ks)


def test_submitted_months_replace_plan_in_full_year() -> None:
    ctx = _ctx()
    plan_oct = ctx.monthly_plan[9]
    with_plan = compute_impact(ctx, EntryInput(month=9, value=1000, low=900, high=1100))
    ctx.submitted = {"10": plan_oct + 500}
    with_submitted = compute_impact(ctx, EntryInput(month=9, value=1000, low=900, high=1100))
    assert with_submitted.fy_estimate - with_plan.fy_estimate == pytest.approx(500)


def test_implausible_number_raises_critical_flags() -> None:
    ctx = _ctx()
    entry = EntryInput(month=9, value=60000, low=58000, high=62000)
    codes = {f.code for f in evaluate_flags(ctx, entry, compute_impact(ctx, entry))}
    assert {"share_over_100", "implied_ha_over_market"} <= codes


def test_wide_range_is_flagged() -> None:
    ctx = _ctx()
    entry = EntryInput(month=9, value=10000, low=6000, high=12000)
    codes = {f.code for f in evaluate_flags(ctx, entry, compute_impact(ctx, entry))}
    assert "range_too_wide" in codes
