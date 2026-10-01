"""SAC GPC Sales (query MDL_LC_FP_Q050): monthly actuals and the reps' IBP forecast by variety.

The SMEs have not shared a sample export yet, so columns are matched by alias and both a long layout (one row
per measure, with an Actual/Forecast column) and a wide layout (separate actual and forecast quantity columns)
are accepted. Fix the aliases here once a real export arrives.
"""

import re
from collections import defaultdict
from datetime import date, datetime

import pandas as pd

from app.constants.demo import MONTH_NAMES
from app.ingest.lookups import ImportContext, normalize
from app.ingest.reader import records, to_datetime, to_float, to_int, to_text
from app.ingest.report import ImportFailure, ImportReport

ALIASES: dict[str, tuple[str, ...]] = {
    "country": ("country_code", "country", "country iso2", "sales country", "country key"),
    "segment": ("micro_segment_id", "microsegment id", "micro segment id", "micro segment", "microsegment"),
    "variety": ("variety", "variety name", "material description", "product", "material"),
    "year": ("year", "fiscal year", "calendar year", "fiscal year/period year"),
    "month": ("month", "fiscal period", "period", "calendar month", "posting period", "calendar year/month"),
    "measure": ("measure", "key figure", "category", "version", "type", "data type"),
    "qty": ("qty_ks", "quantity ks", "qty (ks)", "quantity (ks)", "sales qty", "quantity", "volume ks"),
    "value": ("net_sales_usd", "net sales usd", "net sales", "net value", "sales value", "value_usd"),
    "actual_qty": ("actual_qty_ks", "actual qty", "actual quantity", "actuals ks", "actual qty (ks)"),
    "forecast_qty": ("forecast_qty_ks", "forecast qty", "ibp qty", "forecast quantity", "forecast qty (ks)"),
    "actual_value": ("actual_value_usd", "actual net sales", "actual net sales usd"),
    "forecast_value": ("forecast_value_usd", "forecast net sales", "forecast net sales usd"),
    "snapshot": ("snapshot", "snapshot date", "version date", "forecast version", "ibp snapshot"),
    "planner": ("planner_email", "planner", "demand planner", "sales rep", "rep email"),
    "currency": ("currency", "currency key", "local currency"),
}
NO_VARIETY = "(no variety)"
MONTHS = {m.lower(): i + 1 for i, m in enumerate(MONTH_NAMES)}
PERIOD_PATTERNS = (
    re.compile(r"^(?P<year>\d{4})\s*[/.\-]\s*0?(?P<month>\d{1,2})$"),  # 2026/010, 2026-10, 2026.10
    re.compile(r"^0?(?P<month>\d{1,2})\s*[/.\-]\s*(?P<year>\d{4})$"),  # 010.2026, 10/2026
    re.compile(r"^(?P<year>\d{4})0?(?P<month>\d{2})$"),  # 2026010, 202610
    re.compile(r"^p?0?(?P<month>\d{1,2})$", re.IGNORECASE),  # P10, 010, 10
)


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def column_map(frame: pd.DataFrame) -> dict[str, str]:
    by_key = {_key(c): c for c in frame.columns}
    found = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if _key(alias) in by_key:
                found[canonical] = by_key[_key(alias)]
                break
    return found


def parse_period(value, year_hint: int | None) -> tuple[int, int] | None:
    if isinstance(value, datetime | date):
        return value.year, value.month
    text = to_text(value)
    if text is None:
        return None
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    lowered = text.lower()
    for name, number in MONTHS.items():
        if lowered.startswith(name):
            year = re.search(r"\d{4}", lowered)
            return (int(year.group()) if year else year_hint, number) if (year or year_hint) else None
    for pattern in PERIOD_PATTERNS:
        if match := pattern.match(text):
            month = int(match.group("month"))
            year = int(match.group("year")) if "year" in match.groupdict() else year_hint
            if year and 1 <= month <= 12:
                return year, month
            return None
    return None


def measure_kind(value) -> str | None:
    text = (to_text(value) or "").lower()
    if re.search(r"\bact", text):
        return "actual"
    if re.search(r"fcst|forecast|\bibp\b|demand|latest estimate|\ble\b", text):
        return "forecast"
    return None


def _snapshot(value) -> str | None:
    parsed = to_datetime(value) if not isinstance(value, int | float) else None
    if parsed is not None:
        return parsed.date().isoformat()
    return to_text(value)


def _measures(r: dict, cols: dict[str, str]) -> list[tuple[str, float | None, float | None]]:
    """(measure, qty, value) pairs a row carries in either layout."""
    if "measure" in cols:
        return [(measure_kind(r.get(cols["measure"])), to_float(r.get(cols["qty"])), to_float(r.get(cols.get("value", ""))))]
    out = []
    for measure in ("actual", "forecast"):
        qty_col = cols.get(f"{measure}_qty")
        if qty_col and to_float(r.get(qty_col)) is not None:
            out.append((measure, to_float(r.get(qty_col)), to_float(r.get(cols.get(f"{measure}_value", "")))))
    return out


def validate_sac_sales(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("sac_sales")
    cols = column_map(frame)
    long_layout = "measure" in cols and "qty" in cols
    wide_layout = "actual_qty" in cols or "forecast_qty" in cols
    missing = [n for n in ("country", "month") if n not in cols]
    if not long_layout and not wide_layout:
        missing.append("measure + quantity, or actual/forecast quantity columns")
    if "segment" not in cols and "variety" not in cols:
        missing.append("micro-segment ID or variety")
    if missing:
        raise ImportFailure(f"Missing SAC columns: {', '.join(missing)} (matched: {', '.join(cols) or 'none'})")

    default_snapshot = f"upload-{date.today().isoformat()}"
    actuals: dict[tuple, dict] = {}
    forecasts: dict[tuple, dict] = {}
    unmapped: set[str] = set()
    converted = 0
    for row_no, r in records(frame):
        report.rows_read += 1
        country = ctx.country(r.get(cols["country"]))
        year_hint = to_int(r.get(cols["year"])) if "year" in cols else ctx.current_year
        period = parse_period(r.get(cols["month"]), year_hint)
        variety = to_text(r.get(cols["variety"])) if "variety" in cols else None
        segment_id = to_int(r.get(cols["segment"])) if "segment" in cols else None
        if segment_id is None and variety and country:
            segment_id = ctx.variety_map.get((country, normalize(variety)))
        currency = (to_text(r.get(cols["currency"])) if "currency" in cols else None) or "USD"
        if country is None:
            report.reject(row_no, f"Unknown country '{r.get(cols['country'])}'")
            continue
        if period is None:
            report.reject(row_no, f"Could not read the period '{r.get(cols['month'])}'")
            continue
        if segment_id is None:
            unmapped.add(f"{country} {variety}")
            report.reject(row_no, f"Variety '{variety}' has no micro-segment; upload a variety map")
            continue
        if segment_id not in ctx.segment_ids:
            report.reject(row_no, f"Micro-segment {segment_id} is not in the product hierarchy")
            continue
        pairs = _measures(r, cols)
        if not pairs:
            report.reject(row_no, "No quantity on this row")
            continue
        year, month = period
        for measure, qty, value in pairs:
            if measure is None:
                report.reject(row_no, f"Measure '{r.get(cols['measure'])}' is neither actual nor forecast")
                continue
            if qty is None or qty < 0 or (value is not None and value < 0):
                report.reject(row_no, "Quantity is required and amounts cannot be negative")
                continue
            if value is not None and currency.upper() != "USD":
                usd = ctx.fx.to_usd(value, currency, year)
                if usd is None:
                    report.reject(row_no, f"No budget rate for {currency.upper()} in {year}")
                    continue
                value, converted = usd, converted + 1
            if measure == "actual":
                row = actuals.setdefault(
                    (country, segment_id, year, month),
                    {"measure": "actual", "countryCode": country, "segmentId": segment_id, "year": year,
                     "month": month, "qtyKs": 0.0, "valueUsd": None},
                )
                row["qtyKs"] += qty
                if value is not None:
                    row["valueUsd"] = (row["valueUsd"] or 0.0) + value
            else:
                snapshot = (_snapshot(r.get(cols["snapshot"])) if "snapshot" in cols else None) or default_snapshot
                planner = (to_text(r.get(cols["planner"])) or "").lower() if "planner" in cols else ""
                key = (country, segment_id, variety or NO_VARIETY, year, month, snapshot)
                row = forecasts.setdefault(
                    key,
                    {"measure": "forecast", "countryCode": country, "segmentId": segment_id,
                     "variety": variety or NO_VARIETY, "year": year, "month": month, "snapshot": snapshot,
                     "qtyKs": 0.0, "valueUsd": None, "plannerId": planner or None},
                )
                row["qtyKs"] += qty
                if value is not None:
                    row["valueUsd"] = (row["valueUsd"] or 0.0) + value

    # A forecast is only kept for months still open, counting the months this file's actuals close.
    open_from = dict(ctx.open_from)
    for country, _, year, month in actuals:
        current = open_from.get(country, (year, 1))
        open_from[country] = max(current, (year, month + 1) if month < 12 else (year + 1, 1))
    kept, skipped = {}, 0
    for key, row in forecasts.items():
        if (row["year"], row["month"]) < open_from.get(row["countryCode"], (0, 0)):
            skipped += 1
            continue
        kept[key] = row
    if skipped:
        report.warn("Forecast rows for months that already have actuals were skipped", skipped)
    if converted:
        report.warn("Values converted to USD at the budget rate", converted)

    rows = [*actuals.values(), *kept.values()]
    report.accepted = len(rows)
    report.info = _info(actuals, kept, unmapped, ctx)
    return rows, report


def _info(actuals: dict, forecasts: dict, unmapped: set[str], ctx: ImportContext) -> dict:
    by_variety: dict[str, float] = defaultdict(float)
    rolled: dict[tuple, float] = defaultdict(float)
    for row in forecasts.values():
        by_variety[row["variety"]] += row["qtyKs"]
        rolled[(row["countryCode"], row["segmentId"], row["year"], row["month"])] += row["qtyKs"]
    changes = []
    for key, qty in sorted(rolled.items()):
        previous = ctx.previous_forecast.get(key)
        if previous and abs(previous[1] - qty) > 0.5:
            changes.append(
                {"country": key[0], "segment": key[1], "month": f"{key[2]}-{key[3]:02d}",
                 "previousKs": round(previous[1]), "newKs": round(qty), "previousSnapshot": previous[0]}
            )
    return {
        "actualMonths": sorted({f"{k[2]}-{k[3]:02d}" for k in actuals}),
        "forecastMonths": sorted({f"{r['year']}-{r['month']:02d}" for r in forecasts.values()}),
        "snapshots": sorted({r["snapshot"] for r in forecasts.values()}),
        "countries": sorted({k[0] for k in actuals} | {r["countryCode"] for r in forecasts.values()}),
        "varietyTotalsKs": dict(sorted(((v, round(q)) for v, q in by_variety.items()), key=lambda x: -x[1])[:20]),
        "unmappedVarieties": sorted(unmapped)[:50],
        "changesVsPreviousSnapshot": changes[:30],
    }


def validate_variety_map(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("variety_map")
    cols = column_map(frame)
    missing = [n for n in ("country", "variety", "segment") if n not in cols]
    if missing:
        raise ImportFailure(f"Missing columns: {', '.join(missing)} (expected country_code, variety, micro_segment_id)")
    rows: dict[tuple[str, str], dict] = {}
    for row_no, r in records(frame):
        report.rows_read += 1
        country = ctx.country(r.get(cols["country"]))
        variety = to_text(r.get(cols["variety"]))
        segment_id = to_int(r.get(cols["segment"]))
        if country is None:
            report.reject(row_no, f"Unknown country '{r.get(cols['country'])}'")
        elif not variety:
            report.reject(row_no, "variety is required")
        elif segment_id not in ctx.segment_ids:
            report.reject(row_no, f"Micro-segment {r.get(cols['segment'])} is not in the product hierarchy")
        else:
            key = (country, normalize(variety))
            if key in rows and rows[key]["segmentId"] != segment_id:
                report.warn("A variety mapped to two micro-segments; the last row wins")
            rows[key] = {"countryCode": country, "variety": normalize(variety), "segmentId": segment_id}
    report.accepted = len(rows)
    report.info = {"countries": sorted({k[0] for k in rows}), "varieties": len(rows)}
    return list(rows.values()), report
