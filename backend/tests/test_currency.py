import pytest
from httpx import AsyncClient

from app.ingest.exports import validate_plan
from app.ingest.lookups import ImportContext
from app.ingest.reader import read_upload
from app.ingest.templates import validate_actuals
from app.services.fx_service import BudgetRates

REP_A = {"X-Demo-User": "rep-a"}


def _ctx(**extra) -> ImportContext:
    return ImportContext(
        country_aliases={"ES": "ES", "SPAIN": "ES"},
        segment_ids={2482},
        fx=BudgetRates(by_year={2025: {"EUR": 0.9}, 2026: {"EUR": 0.85}}),
        **extra,
    )


def test_budget_rates_pick_the_year_then_fall_back() -> None:
    fx = BudgetRates(by_year={2025: {"EUR": 0.9}, 2026: {"EUR": 0.85}}, current_year=2026)
    assert fx.to_usd(85, "EUR", 2026) == pytest.approx(100)
    assert fx.to_usd(90, "EUR", 2025) == pytest.approx(100)
    assert fx.to_usd(85, "EUR", 2030) == pytest.approx(100)
    assert fx.to_usd(10, "BRL", 2026) is None
    assert fx.to_usd(10, None, 2026) == 10
    fx.rule = "current_budget"
    assert fx.to_usd(85, "EUR", 2025) == pytest.approx(100)


def test_plan_upload_converts_local_values_and_checks_avg_net_price() -> None:
    csv = (
        "Title,Country,Microsegment ID,Sales Qty,Sales Value,Currency,Avg Net Price\n"
        "2026,Spain,2482,100,42500,EUR,500\n"
        "2025,Spain,2482,100,40000,USD,520\n"
        "2026,Spain,2482,1,1,BRL,\n"
    )
    rows, report = validate_plan(read_upload(csv.encode(), "plan.csv", []), _ctx(current_year=2026))
    by_year = {r["year"]: r for r in rows}
    assert by_year[2026]["valueUsd"] == pytest.approx(50000)
    assert by_year[2026]["netPrice"] == pytest.approx(500)
    assert "No budget rate for BRL" in report.rejects[0]["reason"]
    assert report.info["priceMismatches"] == ["ES 2482 2025"]
    assert report.info["actualYears"] == [2025] and report.info["planYears"] == [2026]

    rows, _ = validate_plan(read_upload(csv.encode(), "plan.csv", []), _ctx(price_source="avg_net_price"))
    assert {r["year"]: r for r in rows}[2025]["netPrice"] == pytest.approx(520)


def test_actuals_accept_the_old_eur_header_and_a_currency_column() -> None:
    old = "country_code,micro_segment_id,year,month,sales_qty_ks,sales_value_eur\nES,2482,2026,9,10,4000\n"
    rows, _ = validate_actuals(read_upload(old.encode(), "a.csv", []), _ctx())
    assert rows[0]["valueUsd"] == 4000
    local = "country_code,micro_segment_id,year,month,sales_qty_ks,sales_value_usd,currency\nES,2482,2026,9,10,850,EUR\n"
    rows, report = validate_actuals(read_upload(local.encode(), "a.csv", []), _ctx())
    assert rows[0]["valueUsd"] == pytest.approx(1000)
    assert any("converted from EUR" in w for w in report.warnings)


async def test_cube_ships_budget_rates_for_display(client: AsyncClient) -> None:
    cube = (await client.get("/api/segments/cube", headers=REP_A)).json()
    assert cube["reportingCurrency"] == "USD"
    assert cube["localCurrency"] == "EUR"
    assert cube["fx"] == {"budgetYear": 2026, "rates": {"USD": 1.0, "EUR": 0.85}}
    meta = (await client.get("/api/meta", headers=REP_A)).json()
    assert meta["reportingCurrency"] == "USD" and meta["defaultDisplayCurrency"] == "USD"
