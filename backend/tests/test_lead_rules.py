import json
from pathlib import Path

from httpx import AsyncClient

from app.schemas.demand_math import EntryInput, LeadRuleSpec, SegmentContext
from app.schemas.rules import RuleSlots
from app.services.demand_math import compute_impact
from app.services.lead_rules import evaluate_rules
from app.services.rule_service import describe, month_span, parse_months, parse_threshold

LEAD = {"X-Demo-User": "lead"}
REP_A = {"X-Demo-User": "rep-a"}
RULE_TEXT = (
    "Do not accept autumn increases above 20% over last year for any segment "
    "unless the rep names a competitor move."
)
COMPETITOR = "Two Almeria cooperatives are switching from Sur Seeds to Leontes after a competitor supply shortage."
PRICE = "Our price is lower this season so growers will buy more."
CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "lead_rule_cases.json").read_text()
)


def test_parse_months() -> None:
    assert parse_months("autumn increases") == [9, 10, 11]
    assert parse_months("from Nov to Feb") == [1, 2, 11, 12]
    assert parse_months("October and December only") == [10, 12]
    assert parse_months("reps may raise numbers") is None
    assert parse_months("No month here") is None


def test_parse_threshold() -> None:
    assert parse_threshold("above 20% over last year") == 20
    assert parse_threshold("more than 7.5 pts of share") == 7.5
    assert parse_threshold("in 2025 the numbers were off") is None


def test_describe_reads_back_the_slots() -> None:
    slots = RuleSlots(
        metric="month_vs_last_year_pct",
        comparator="above",
        threshold=20,
        months=[9, 10, 11],
        required_driver="competitor_move",
        severity="critical",
    )
    text = describe(slots, {}, "Blocky PGH")
    assert text == (
        "For every micro-segment of Blocky PGH in Sep-Nov, flag entries where the month vs the same month last "
        "year is above +20%; the justification must cite a competitor move (hard stop)."
    )
    assert month_span([12, 1, 2, 6]) == "Dec-Feb, Jun"


def test_rule_cases_match_fixture() -> None:
    for case in CASES:
        ctx = SegmentContext.model_validate(case["context"])
        entry = EntryInput.model_validate(case["entry"])
        rules = [LeadRuleSpec.model_validate(r) for r in case["rules"]]
        flags = evaluate_rules(ctx, case["segmentId"], entry, compute_impact(ctx, entry), rules)
        assert [f.message for f in flags] == case["expectedMessages"], case["name"]


async def _cube(client: AsyncClient) -> dict:
    return (await client.get("/api/segments/cube", headers=LEAD)).json()


async def test_lead_rule_lifecycle(client: AsyncClient) -> None:
    cube = await _cube(client)
    scope = {"countryCode": cube["countryCode"], "megaSegmentId": cube["megaSegmentId"]}

    assert (await client.post("/api/rules/compile", json={**scope, "text": RULE_TEXT}, headers=REP_A)).status_code == 403

    draft = (await client.post("/api/rules/compile", json={**scope, "text": RULE_TEXT}, headers=LEAD)).json()
    assert draft["ok"], draft
    assert draft["slots"] == {
        "metric": "month_vs_last_year_pct",
        "comparator": "above",
        "threshold": 20.0,
        "months": [9, 10, 11],
        "segmentIds": None,
        "requiredDriver": "competitor_move",
        "severity": "critical",
    }
    assert draft["preview"]["checked"] == 0  # the seeded history covers Jan-Aug only

    year_round = (
        await client.post(
            "/api/rules/compile",
            json={**scope, "text": "Flag any segment where the month is more than 20% above last year"},
            headers=LEAD,
        )
    ).json()
    preview = year_round["preview"]
    assert preview["checked"] > 0 and preview["fired"] == preview["confirmed"] + preview["contradicted"]

    vague = (await client.post("/api/rules/compile", json={**scope, "text": "Be more careful with autumn numbers"}, headers=LEAD)).json()
    assert not vague["ok"] and vague["rejection"]

    created = await client.post(
        "/api/rules",
        json={**scope, "text": RULE_TEXT, "slots": draft["slots"], "provider": draft["provider"], "decisions": draft["decisions"]},
        headers=LEAD,
    )
    assert created.status_code == 201
    rule = created.json()
    code = f"lead_rule_{rule['id']}"

    cube = await _cube(client)
    assert [r["id"] for r in cube["rules"]] == [rule["id"]]
    ctx = next(s for s in cube["segments"] if s["id"] == 2482)["context"]
    value = round(ctx["lastYearMonthly"][8] * 1.5)
    body = {"segmentId": 2482, "month": 9, "value": value, "low": round(value * 0.95), "high": round(value * 1.05)}

    priced = (await client.post("/api/justifications/analyze", json={**body, "justification": PRICE})).json()
    assert code in {f["code"] for f in priced["flags"]}
    assert f"{code}_unmet" in {f["code"] for f in priced["claim"]["mismatches"]}

    saved = (await client.post("/api/entries", json={**body, "justification": COMPETITOR}, headers=REP_A)).json()
    codes = {f["code"] for f in saved["flags"]}
    assert code in codes and f"{code}_unmet" not in codes

    listed = (await client.get(f"/api/rules?country={scope['countryCode']}&mega={scope['megaSegmentId']}")).json()
    assert listed[0]["stats"]["fired"] == 1

    assert (await client.post(f"/api/rules/{rule['id']}/retire", headers=REP_A)).status_code == 403
    assert (await client.post(f"/api/rules/{rule['id']}/retire", headers=LEAD)).status_code == 204
    assert (await _cube(client))["rules"] == []


async def test_rule_slots_are_validated(client: AsyncClient) -> None:
    cube = await _cube(client)
    body = {
        "countryCode": cube["countryCode"],
        "megaSegmentId": cube["megaSegmentId"],
        "text": "Flag big jumps of more than 10 pts",
        "provider": "offline decider",
        "slots": {"metric": "made_up", "comparator": "above", "threshold": 10, "severity": "warning", "segmentIds": [1]},
    }
    response = await client.post("/api/rules", json=body, headers=LEAD)
    assert response.status_code == 422
    assert "unknown measure" in response.json()["detail"]
