from datetime import date

from httpx import AsyncClient
from sqlalchemy import update

from app.database import async_session
from app.models import MarketYear
from app.services.resolution_service import numeric_support
from app.services.upload_service import _past_hold

ADMIN = {"X-Demo-User": "admin"}
REP_A = {"X-Demo-User": "rep-a"}


async def test_admin_can_set_every_assumption(client: AsyncClient) -> None:
    defaults = (await client.get("/api/admin/settings", headers=ADMIN)).json()
    assert defaults["priceSource"] == "value_over_qty"
    assert defaults["marketZeroMeans"] == "no_market"
    assert defaults["claimBaseline"] == "plan" and defaults["claimNeutralTolerancePct"] == 5
    assert defaults["demandSource"] == "manual" and defaults["reportingCurrency"] == "USD"
    patch = {
        "priceSource": "avg_net_price",
        "marketZeroMeans": "missing",
        "actualsHoldDays": 10,
        "fxRateYearRule": "current_budget",
        "claimBaseline": "rep_number",
        "claimNeutralTolerancePct": 8,
        "defaultDisplayCurrency": "EUR",
    }
    saved = (await client.put("/api/admin/settings", json=patch, headers=ADMIN)).json()
    assert {k: saved[k] for k in patch} == patch
    assert (await client.put("/api/admin/settings", json={"actualsHoldDays": -1}, headers=ADMIN)).status_code == 422
    assert (await client.put("/api/admin/settings", json={"claimBaseline": "x"}, headers=ADMIN)).status_code == 422


async def test_zero_hectare_segments_show_when_zero_means_missing(client: AsyncClient) -> None:
    async with async_session() as db:
        await db.execute(update(MarketYear).where(MarketYear.segment_id == 2483).values(hectares=0.0))
        await db.commit()
    ids = {s["id"] for s in (await client.get("/api/segments/cube", headers=REP_A)).json()["segments"]}
    assert 2483 not in ids
    await client.put("/api/admin/settings", json={"marketZeroMeans": "missing"}, headers=ADMIN)
    ids = {s["id"] for s in (await client.get("/api/segments/cube", headers=REP_A)).json()["segments"]}
    assert 2483 in ids


def test_claims_can_be_scored_against_the_rep_number() -> None:
    assert numeric_support("up", actual=120, plan=100)
    assert not numeric_support("up", actual=120, plan=100, rep_value=150, baseline="rep_number", tolerance=0.05)
    assert numeric_support("down", actual=148, plan=100, rep_value=150, baseline="rep_number", tolerance=0.05)
    assert numeric_support("neutral", actual=107, plan=100, tolerance=0.08)
    assert not numeric_support("neutral", actual=107, plan=100)


def test_actuals_hold_waits_for_the_month_to_age() -> None:
    assert not _past_hold(2026, 9, 10, date(2026, 10, 5))
    assert _past_hold(2026, 9, 10, date(2026, 10, 10))
    assert _past_hold(2026, 9, 0, date(2026, 9, 30))
