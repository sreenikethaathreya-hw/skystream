from pathlib import Path

import pytest

from app.ingest.lookups import ImportContext
from app.ingest.reader import read_upload
from app.ingest.report import ImportFailure
from app.ingest.sac import parse_period, validate_sac_sales, validate_variety_map
from app.services.fx_service import BudgetRates

UPLOADS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uploads"


def _ctx(**extra) -> ImportContext:
    return ImportContext(
        country_aliases={"ES": "ES", "SPAIN": "ES"},
        segment_ids={2481, 2482},
        fx=BudgetRates(by_year={2026: {"EUR": 0.85}}),
        current_year=2026,
        open_from={"ES": (2026, 9)},
        **extra,
    )


def _run(content: str | bytes, ctx: ImportContext, name: str = "sac.csv"):
    data = content.encode() if isinstance(content, str) else content
    return validate_sac_sales(read_upload(data, name, []), ctx)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2026/010", (2026, 10)), ("010.2026", (2026, 10)), ("2026-10", (2026, 10)), ("202610", (2026, 10)),
     ("P10", (2026, 10)), ("10", (2026, 10)), (10.0, (2026, 10)), ("Oct", (2026, 10)), ("October 2027", (2027, 10)),
     ("13/2026", None), ("", None)],
)
def test_parse_period_formats(value, expected) -> None:
    assert parse_period(value, 2026) == expected


def test_long_layout_splits_actuals_and_forecast() -> None:
    rows, report = _run((UPLOADS / "sac_sales.csv").read_bytes(), _ctx())
    actual = [r for r in rows if r["measure"] == "actual"]
    forecast = [r for r in rows if r["measure"] == "forecast"]
    assert actual == [{"measure": "actual", "countryCode": "ES", "segmentId": 2482, "year": 2026, "month": 8,
                       "qtyKs": 12900.0, "valueUsd": 5805000.0}]
    assert {(r["variety"], r["month"]) for r in forecast} == {("Leontes", 10), ("Hokkaido", 10), ("Leontes", 11)}
    nov = next(r for r in forecast if r["month"] == 11)
    assert nov["valueUsd"] == pytest.approx(17000000 / 0.85)
    assert nov["plannerId"] == "ana.rep@example.com" and nov["snapshot"] == "2026-09-28"
    reasons = " ".join(r["reason"] for r in report.rejects)
    assert "Bokken" in reasons and "Atlantis" in reasons and "13/2026" in reasons and "Budget" in reasons
    assert report.info["unmappedVarieties"] == ["ES Bokken"]
    assert report.info["varietyTotalsKs"]["Leontes"] == 42000
    assert any("already have actuals" in w for w in report.warnings)


def test_variety_map_fills_the_micro_segment() -> None:
    csv = "country,variety,month,measure,qty_ks\nES,BOKKEN ,2026/010,Forecast,800\n"
    rows, report = _run(csv, _ctx(variety_map={("ES", "BOKKEN"): 2481}))
    assert report.rejected == 0 and rows[0]["segmentId"] == 2481


def test_wide_layout_and_changes_against_the_previous_snapshot() -> None:
    csv = (
        "Country,Microsegment ID,Variety,Period,Actual Qty,Forecast Qty,Snapshot\n"
        "ES,2482,Leontes,2026-10,,2500,2026-10-28\n"
        "ES,2482,Leontes,2026-09,1200,,2026-10-28\n"
    )
    ctx = _ctx(previous_forecast={("ES", 2482, 2026, 10): ("2026-09-28", 2000.0)})
    rows, report = _run(csv, ctx)
    assert {r["measure"] for r in rows} == {"actual", "forecast"}
    assert report.info["changesVsPreviousSnapshot"] == [
        {"country": "ES", "segment": 2482, "month": "2026-10", "previousKs": 2000, "newKs": 2500,
         "previousSnapshot": "2026-09-28"}
    ]


def test_missing_columns_fail_with_what_was_matched() -> None:
    with pytest.raises(ImportFailure, match="Missing SAC columns"):
        _run("Country,Amount\nES,1\n", _ctx())


def test_variety_map_validator() -> None:
    csv = "country_code,variety,micro_segment_id\nES,Leontes,2482\nES,Hokkaido,9999\nXX,Bokken,2481\n"
    rows, report = validate_variety_map(read_upload(csv.encode(), "map.csv", []), _ctx())
    assert rows == [{"countryCode": "ES", "variety": "LEONTES", "segmentId": 2482}]
    assert report.rejected == 2
