"""Finance budget rates: the 'BUD <year>' workbook as finance sends it, or the CSV template."""

import re

import pandas as pd

from app.ingest.lookups import ImportContext
from app.ingest.reader import FIRST_DATA_ROW, records, to_float, to_int, to_text
from app.ingest.report import ImportFailure, ImportReport

BUDGET_YEAR = re.compile(r"\bBUD\s*(\d{4})\b", re.IGNORECASE)
CODE = re.compile(r"^[A-Z]{3}$")
TEMPLATE_COLUMNS = {"budget_year", "currency", "per_usd"}
# Workbook layout: column B currency name, C ISO code, D units per 1 USD. The cross-rate block and notes sit
# further right and are ignored.
NAME_COL, CODE_COL, RATE_COL = 1, 2, 3


def _workbook_year(frame: pd.DataFrame) -> int | None:
    for text in [frame.attrs.get("sheet", ""), *map(str, frame.columns)]:
        if match := BUDGET_YEAR.search(text):
            return int(match.group(1))
    for row in frame.itertuples(index=False):
        for cell in row:
            if isinstance(cell, str) and (match := BUDGET_YEAR.search(cell)):
                return int(match.group(1))
    return None


def _template_rows(frame: pd.DataFrame) -> list[tuple[int, int | None, str | None, str | None, float | None]]:
    return [
        (
            row_no,
            to_int(r.get("budget_year")),
            (to_text(r.get("currency")) or "").upper() or None,
            to_text(r.get("currency_name")),
            to_float(r.get("per_usd")),
        )
        for row_no, r in records(frame)
    ]


def _workbook_rows(frame: pd.DataFrame) -> list[tuple[int, int | None, str | None, str | None, float | None]]:
    if frame.shape[1] <= RATE_COL:
        raise ImportFailure("Expected the finance layout: currency name in B, code in C, rate per USD in D")
    year = _workbook_year(frame)
    if year is None:
        raise ImportFailure("Could not find the budget year: name the sheet 'BUD <year>' or use the template")
    out = []
    for i, row in enumerate(frame.itertuples(index=False)):
        code = to_text(row[CODE_COL])
        if code is None or not CODE.match(code):
            continue
        out.append((i + FIRST_DATA_ROW, year, code, to_text(row[NAME_COL]), to_float(row[RATE_COL])))
    return out


def validate_budget_rates(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("budget_rates")
    columns = {c.lower() for c in frame.columns}
    if TEMPLATE_COLUMNS <= columns:
        frame = frame.rename(columns={c: c.lower() for c in frame.columns})
        raw = _template_rows(frame)
    else:
        raw = _workbook_rows(frame)

    rows: dict[tuple[int, str], dict] = {}
    for row_no, year, code, name, rate in raw:
        report.rows_read += 1
        if year is None or not 1990 <= year <= 2100:
            report.reject(row_no, "budget_year must be a four-digit year")
        elif code is None or not CODE.match(code):
            report.reject(row_no, f"'{code}' is not a three-letter currency code")
        elif rate is None or rate <= 0:
            report.reject(row_no, f"{code}: the rate per USD must be a positive number")
        elif (year, code) in rows:
            report.reject(row_no, f"{code} appears twice for {year}")
        elif code == "USD" and abs(rate - 1) > 1e-9:
            report.reject(row_no, "USD must be 1 per USD")
        else:
            rows[(year, code)] = {"budgetYear": year, "currency": code, "currencyName": name, "perUsd": rate}

    years = sorted({y for y, _ in rows})
    missing_usd = [y for y in years if (y, "USD") not in rows]
    if missing_usd:
        raise ImportFailure(f"No USD row for {', '.join(map(str, missing_usd))}; money is stored in USD")
    report.accepted = len(rows)
    report.info = {
        "budgetYears": years,
        "currencies": len({c for _, c in rows}),
        "eurPerUsd": next((r["perUsd"] for (y, c), r in rows.items() if c == "EUR"), None),
    }
    return list(rows.values()), report
