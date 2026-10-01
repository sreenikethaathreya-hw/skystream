from pathlib import Path

import pytest

from app.ingest.lookups import ImportContext, normalize
from app.ingest.reader import read_upload
from app.ingest.registry import UPLOAD_KINDS
from app.ingest.report import ImportFailure

UPLOADS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uploads"


def run(kind: str, filename: str, ctx: ImportContext):
    content = (UPLOADS / filename).read_bytes()
    frame = read_upload(content, filename, list(UPLOAD_KINDS[kind].sheets))
    return UPLOAD_KINDS[kind].validator(frame, ctx)


@pytest.fixture
def ctx() -> ImportContext:
    context = ImportContext(
        country_aliases={"ES": "ES", "SPAIN": "ES", "PT": "PT", "PORTUGAL": "PT"}, grower_ha_cap=500.0
    )
    rows, _ = run("hierarchy", "hierarchy.csv", context)
    for r in rows:
        context.segment_ids.add(r["id"])
        context.segment_by_desc[normalize(r["description"])] = r["id"]
        context.mega_by_segment[r["id"]] = r["megaSegmentId"]
    return context


def test_hierarchy_rejects_rows_without_ids(ctx: ImportContext) -> None:
    rows, report = run("hierarchy", "hierarchy.csv", ctx)
    assert {r["id"] for r in rows} == {2482, 2432, 3001}
    assert report.rejected == 1
    assert next(r for r in rows if r["id"] == 2482)["profile"] == "autumn_late"


def test_market_dedupes_by_modified_and_rejects_unknowns(ctx: ImportContext) -> None:
    rows, report = run("market", "market.csv", ctx)
    es_2026 = next(r for r in rows if (r["countryCode"], r["segmentId"], r["year"]) == ("ES", 2482, 2026))
    assert es_2026["hectares"] == 3300
    assert es_2026["notes"]["dynamics"] == "T. parvispinus pressure"
    reasons = " ".join(r["reason"] for r in report.rejects)
    assert "Unknown country 'Atlantis'" in reasons and "9999" in reasons
    assert report.info["countries"] == ["ES", "PT"]
    assert report.info["conflictingDuplicates"] == 1


def test_plan_recovers_ids_from_descriptions_and_computes_net_price(ctx: ImportContext) -> None:
    rows, report = run("plan", "plan.csv", ctx)
    recovered = next(r for r in rows if (r["countryCode"], r["segmentId"], r["year"]) == ("ES", 2432, 2026))
    assert recovered["netPrice"] == pytest.approx(386.0)
    assert report.info["idsRecoveredFromDescription"] == 1
    assert report.rejected == 1


def test_competitors_normalize_syngenta_and_warn_on_bad_totals(ctx: ImportContext) -> None:
    rows, report = run("competitors", "competitors.csv", ctx)
    assert {r["competitor"] for r in rows if r["countryCode"] == "ES"} == {
        "Syngenta",
        "Limagrain",
        "Sur Seeds",
    }
    assert any("do not sum to 100" in w for w in report.warnings)


def test_grower_caps_outliers_and_classifies_owner(ctx: ImportContext) -> None:
    rows, report = run("grower", "grower.csv", ctx)
    assert max(r["hectares"] for r in rows) == 500
    assert {r["owner"] for r in rows} == {"syngenta", "competitor"}
    assert report.warnings["Rows above 500 ha capped"] == 1


def test_actuals_validate_month_and_country(ctx: ImportContext) -> None:
    rows, report = run("actuals", "actuals_2025.csv", ctx)
    assert len(rows) == 18
    assert report.rejected == 2
    assert any(r["valueUsd"] is None for r in rows)


def test_assignments_reject_bad_roles(ctx: ImportContext) -> None:
    rows, report = run("assignments", "assignments.csv", ctx)
    assert {r["email"] for r in rows} == {"ana@example.com", "pedro@example.com", "lead@example.com"}
    assert report.rejected == 1
    pedro = next(r for r in rows if r["email"] == "pedro@example.com")
    assert pedro["scopes"] == [{"countryCode": "PT", "scopeType": "mega", "scopeId": "SP01"}]


def test_seasonality_normalizes_weights(ctx: ImportContext) -> None:
    rows, _ = run("seasonality", "seasonality.csv", ctx)
    assert len(rows) == 12
    assert sum(r["weight"] for r in rows) == pytest.approx(1.0)


def test_missing_required_columns_fail_the_whole_file(ctx: ImportContext) -> None:
    frame = read_upload(b"Country,Year\nSpain,2026\n", "bad.csv", [])
    with pytest.raises(ImportFailure, match="Missing required columns"):
        UPLOAD_KINDS["market"].validator(frame, ctx)


def test_unsupported_file_type_fails() -> None:
    with pytest.raises(ImportFailure, match=".xlsx or .csv"):
        read_upload(b"x", "notes.txt", [])
