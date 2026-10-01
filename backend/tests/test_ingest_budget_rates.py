from pathlib import Path

import pytest

from app.ingest.fx import validate_budget_rates
from app.ingest.lookups import ImportContext
from app.ingest.reader import read_upload
from app.ingest.report import ImportFailure

ROOT = Path(__file__).resolve().parents[2]
UPLOADS = ROOT / "tests" / "fixtures" / "uploads"
# The real finance file is internal; it lives in the gitignored data/raw/ and is only checked when present.
REAL_FILE = ROOT / "data" / "raw" / "2026 budget rates.xlsx"


def _csv(text: str):
    return validate_budget_rates(read_upload(text.encode(), "rates.csv", []), ImportContext())


def _workbook(path: Path):
    return validate_budget_rates(read_upload(path.read_bytes(), path.name, []), ImportContext())


def test_reads_the_finance_workbook_layout() -> None:
    rows, report = _workbook(UPLOADS / "budget_rates_2026.xlsx")
    by_code = {r["currency"]: r for r in rows}
    assert report.rejected == 0, report.rejects
    assert len(rows) == 8
    assert {r["budgetYear"] for r in rows} == {2026}
    assert by_code["USD"]["perUsd"] == 1
    assert by_code["EUR"]["perUsd"] == pytest.approx(0.85)
    assert by_code["EUR"]["currencyName"] == "Euro"
    assert report.info["eurPerUsd"] == pytest.approx(0.85)


@pytest.mark.skipif(not REAL_FILE.exists(), reason="finance budget-rate file not in data/raw/")
def test_reads_the_real_finance_file() -> None:
    rows, report = _workbook(REAL_FILE)
    assert report.rejected == 0, report.rejects
    assert len(rows) == 85
    assert {r["budgetYear"] for r in rows} == {2026}
    assert {r["currency"]: r["perUsd"] for r in rows}["USD"] == 1


def test_template_rows_are_checked() -> None:
    rows, report = _csv(
        "budget_year,currency,currency_name,per_usd\n"
        "2026,USD,US Dollar,1\n2026,EUR,Euro,0.85\n2026,EUR,Euro,0.86\n"
        "2026,GBP,Pound,0\n2026,usdx,Bad,2\n2026,USD,Dup,1\n"
    )
    assert {r["currency"] for r in rows} == {"USD", "EUR"}
    reasons = " ".join(r["reason"] for r in report.rejects)
    assert "EUR appears twice" in reasons and "positive" in reasons and "three-letter" in reasons


def test_usd_row_is_required_and_must_be_one() -> None:
    with pytest.raises(ImportFailure, match="No USD row"):
        _csv("budget_year,currency,per_usd\n2026,EUR,0.85\n")
    with pytest.raises(ImportFailure, match="No USD row"):
        _csv("budget_year,currency,per_usd\n2026,USD,1.1\n2026,EUR,0.85\n")
