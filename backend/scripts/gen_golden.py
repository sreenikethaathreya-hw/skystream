"""Regenerate tests/fixtures/demand_math_cases.json from the seed data and the Python math.

Run from backend/: `uv run python scripts/gen_golden.py`. The TS suite asserts the same outputs.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.ingest.lookups import ImportContext  # noqa: E402
from app.ingest.reader import read_upload  # noqa: E402
from app.ingest.registry import UPLOAD_KINDS  # noqa: E402
from app.models import CompetitorShare, MarketYear, MonthlyPlan, PlanYear, Segment  # noqa: E402
from app.schemas.demand_math import EntryInput, LeadRuleSpec  # noqa: E402
from app.services.cube_builder import Reference, build_mega, build_segment_context  # noqa: E402
from app.services.demand_math import compute_impact  # noqa: E402
from app.services.flags import evaluate_flags  # noqa: E402
from app.services.lead_rules import evaluate_rules  # noqa: E402
from app.services.seed_service import read_seed, reference_from_seed  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "demand_math_cases.json"
RULES_OUT = OUT.parent / "lead_rule_cases.json"
UPLOADS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uploads"


def portugal_context():
    """A second country built through the real upload validators (tests/fixtures/uploads), flat monthly plan."""
    ctx = ImportContext(country_aliases={"ES": "ES", "SPAIN": "ES", "PT": "PT", "PORTUGAL": "PT"})

    def rows(kind: str, filename: str) -> list[dict]:
        content = (UPLOADS / filename).read_bytes()
        return UPLOAD_KINDS[kind].validator(read_upload(content, filename, []), ctx)[0]

    for h in rows("hierarchy", "hierarchy.csv"):
        ctx.segment_ids.add(h["id"])
        ctx.mega_by_segment[h["id"]] = h["megaSegmentId"]
    segments = [
        Segment(id=2482, mega_segment_id="SP01", description="", mega_segment_desc="", profile="autumn_late")
    ]
    market = [
        MarketYear(**_orm(m), notes=m["notes"])
        for m in rows("market", "market.csv")
        if m["countryCode"] == "PT" and m["segmentId"] == 2482
    ]
    plan = [
        PlanYear(**_orm(p))
        for p in rows("plan", "plan.csv")
        if p["countryCode"] == "PT" and p["segmentId"] == 2482
    ]
    monthly = [
        MonthlyPlan(segment_id=2482, year=p.year, month=m, qty_ks=p.qty_ks / 12)
        for p in plan
        for m in range(1, 13)
    ]
    competitors = [
        CompetitorShare(competitor=c["competitor"], year=c["year"], share_pct=c["sharePct"])
        for c in rows("competitors", "competitors.csv")
        if c["countryCode"] == "PT"
    ]
    ref = Reference(
        segments=segments, market=market, plan=plan, monthly_plan=monthly, competitors=competitors
    )
    return build_segment_context(ref, 2482, 2026, 3, {}, build_mega(ref, 2026))


def _orm(row: dict) -> dict:
    keys = {
        "segmentId": "segment_id",
        "year": "year",
        "hectares": "hectares",
        "qtyKs": "qty_ks",
        "density": "density",
        "priceExseed": "price_exseed",
        "priceFarmgate": "price_farmgate",
        "valueUsd": "value_usd",
        "netPrice": "net_price",
        "fpiQtyKs": "fpi_qty_ks",
        "comment": "comment",
    }
    return {keys[k]: v for k, v in row.items() if k in keys}


def main() -> None:
    seed_dir = get_settings().seed_dir
    ref = reference_from_seed(seed_dir)
    meta = read_seed(seed_dir, "meta")
    year, clock = meta["currentYear"], meta["clockStartMonth"]
    mega = build_mega(ref, year)

    def ctx(segment_id: int, submitted: dict[int, float] | None = None):
        return build_segment_context(ref, segment_id, year, clock, submitted or {}, mega)

    def plan_month(segment_id: int, month: int) -> float:
        return ctx(segment_id).monthly_plan[month - 1]

    p2482 = plan_month(2482, 9)
    p2448 = plan_month(2448, 10)
    cases = [
        ("2482 at plan", ctx(2482), EntryInput(month=9, value=p2482, low=p2482 * 0.95, high=p2482 * 1.05)),
        (
            "2482 raised 25%",
            ctx(2482),
            EntryInput(month=9, value=p2482 * 1.25, low=p2482 * 1.15, high=p2482 * 1.3),
        ),
        ("2482 unrealistic", ctx(2482), EntryInput(month=9, value=40000, low=38000, high=42000)),
        (
            "2482 wide range, high price",
            ctx(2482),
            EntryInput(month=9, value=p2482, low=p2482 * 0.6, high=p2482 * 1.2, price=900),
        ),
        (
            "2482 volume cut at premium price",
            ctx(2482),
            EntryInput(month=9, value=p2482 * 0.5, low=p2482 * 0.45, high=p2482 * 0.55, price=560),
        ),
        (
            "2448 raised in shrinking area",
            ctx(2448),
            EntryInput(month=10, value=p2448 * 3, low=p2448 * 2.8, high=p2448 * 3.2),
        ),
        (
            "2482 beyond the whole mega-segment",
            ctx(2482),
            EntryInput(month=9, value=250000, low=240000, high=260000),
        ),
        (
            "2432 storyboard: October lifts share 20% to 35%",
            ctx(2432),
            EntryInput(month=10, value=7090, low=6700, high=7500),
        ),
        (
            "2432 with submitted months",
            ctx(2432, {10: 2600.0, 11: 2500.0}),
            EntryInput(month=12, value=1300, low=1200, high=1400),
        ),
    ]

    portugal = portugal_context()
    pt_plan = portugal.monthly_plan[2]
    cases.append(
        (
            "PT 2482 from uploads, flat plan, no actuals",
            portugal,
            EntryInput(month=3, value=pt_plan * 1.4, low=pt_plan * 1.3, high=pt_plan * 1.5),
        )
    )

    payload = []
    for name, context, entry in cases:
        impact = compute_impact(context, entry)
        flags = evaluate_flags(context, entry, impact)
        payload.append(
            {
                "name": name,
                "context": context.model_dump(by_alias=True),
                "entry": entry.model_dump(by_alias=True),
                "expected": impact.model_dump(by_alias=True),
                "expectedFlags": [f.code for f in flags],
                "expectedMessages": [f.message for f in flags],
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1))
    for case in payload:
        print(f"{case['name']}: {case['expectedFlags']}")

    def rule(rule_id: int, metric: str, comparator: str, threshold: float, **extra) -> LeadRuleSpec:
        return LeadRuleSpec(
            id=rule_id,
            metric=metric,
            comparator=comparator,
            threshold=threshold,
            severity=extra.pop("severity", "warning"),
            description=f"Rule {rule_id}.",
            author="Lead",
            **extra,
        )

    rule_cases = [
        (
            "2432 storyboard against lead rules",
            2432,
            ctx(2432),
            EntryInput(month=10, value=7090, low=6700, high=7500),
            [
                rule(1, "month_vs_last_year_pct", "above", 20, months=[10, 11]),
                rule(2, "month_vs_last_year_pct", "above", 20, segment_ids=[2482]),
                rule(3, "share_jump_pts", "above", 10, severity="critical"),
                rule(4, "price_vs_plan_pct", "below", -10),
                rule(5, "month_vs_average_pct", "above", 50, months=[3]),
            ],
        ),
        (
            "2482 at plan, premium price, narrow range",
            2482,
            ctx(2482),
            EntryInput(month=9, value=p2482, low=p2482 * 0.95, high=p2482 * 1.05, price=900),
            [
                rule(6, "price_vs_plan_pct", "above", 5),
                rule(7, "range_width_pct", "above", 5),
                rule(8, "volume_share_pct", "below", 1),
                rule(9, "month_vs_plan_pct", "below", -5),
            ],
        ),
    ]
    rule_payload = []
    for name, segment_id, context, entry, rules in rule_cases:
        impact = compute_impact(context, entry)
        rule_payload.append(
            {
                "name": name,
                "segmentId": segment_id,
                "context": context.model_dump(by_alias=True),
                "entry": entry.model_dump(by_alias=True),
                "rules": [r.model_dump(by_alias=True) for r in rules],
                "expectedMessages": [
                    f.message for f in evaluate_rules(context, segment_id, entry, impact, rules)
                ],
            }
        )
    RULES_OUT.write_text(json.dumps(rule_payload, indent=1))
    for case in rule_payload:
        print(f"{case['name']}: {case['expectedMessages']}")


if __name__ == "__main__":
    main()
