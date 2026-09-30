"""Validators for the competitor share list and the CRM grower-potential export."""

from collections import defaultdict

import pandas as pd

from app.ingest.lookups import ImportContext
from app.ingest.reader import YEAR_PCT, records, require_columns, to_float, to_text
from app.ingest.report import ImportFailure, ImportReport

SHARE_TOLERANCE_PTS = 1.0


def validate_competitors(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("competitors")
    require_columns(frame, ["Forecast Customer Country_D", "Mega_Segment_Id", "CompetitorDesc"])
    years = sorted(int(m.group(1)) for c in frame.columns if (m := YEAR_PCT.match(c)))
    if not years:
        raise ImportFailure("No share columns found (expected columns like 2026%)")
    rows: dict[tuple, dict] = {}
    rows_used = 0
    for row_no, r in records(frame):
        report.rows_read += 1
        produced = False
        country = ctx.country(r.get("Forecast Customer Country_D"))
        mega = to_text(r.get("Mega_Segment_Id"))
        name = to_text(r.get("CompetitorDesc"))
        if country is None:
            report.reject(row_no, f"Unknown country '{r.get('Forecast Customer Country_D')}'")
            continue
        if not mega or not name:
            report.reject(row_no, "Mega_Segment_Id and CompetitorDesc are required")
            continue
        if mega not in ctx.mega_ids:
            report.warn("Mega-segment not in the product hierarchy; rows kept but unused until it is")
        if name.lower() == "syngenta":
            name = "Syngenta"
        for year in years:
            pct = to_float(r.get(f"{year}%"))
            if pct is None:
                continue
            if not 0 <= pct <= 100:
                report.warn("Share outside 0-100 ignored for that year")
                continue
            key = (country, mega, name, year)
            if key in rows:
                report.warn("Duplicate competitor/year; the last row wins")
            rows[key] = {
                "countryCode": country,
                "megaSegmentId": mega,
                "competitor": name,
                "year": year,
                "sharePct": pct,
                "valueEur": to_float(r.get(str(year))) or 0.0,
                "trend": to_text(r.get("CompetitorTrend")),
            }
            produced = True
        if produced:
            rows_used += 1
        else:
            report.reject(row_no, "No usable yearly share")
    totals: dict[tuple, float] = defaultdict(float)
    for row in rows.values():
        totals[(row["countryCode"], row["megaSegmentId"], row["year"])] += row["sharePct"]
    off = sum(1 for total in totals.values() if total and abs(total - 100) > SHARE_TOLERANCE_PTS)
    if off:
        report.warn("Mega-segment/year shares do not sum to 100 (+/- 1 pt)", off)
    report.accepted = rows_used
    report.info = {"megaSegments": len({k[1] for k in rows}), "years": years, "shareRecords": len(rows)}
    return list(rows.values()), report


def validate_grower(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("grower")
    require_columns(frame, ["Country Name", "Crop Local", "Hecatres Info."])
    rows = []
    capped = 0
    for row_no, r in records(frame):
        report.rows_read += 1
        country = ctx.country(r.get("Country Name"))
        crop = to_text(r.get("Crop Local"))
        hectares = to_float(r.get("Hecatres Info."))
        if country is None:
            report.reject(row_no, f"Unknown country '{r.get('Country Name')}'")
            continue
        if not crop or hectares is None or hectares < 0:
            report.reject(row_no, "Crop Local and a non-negative Hecatres Info. are required")
            continue
        if hectares > ctx.grower_ha_cap:
            capped += 1
            hectares = ctx.grower_ha_cap
        competitor = to_text(r.get("Competitor"))
        owner = (
            "unknown" if not competitor else "syngenta" if competitor.upper() == "SYNGENTA" else "competitor"
        )
        rows.append(
            {
                "countryCode": country,
                "cropLocal": crop.upper(),
                "variety": to_text(r.get("Variety")),
                "owner": owner,
                "hectares": hectares,
                "density": to_float(r.get("Density")) or 0.0,
                "region": to_text(r.get("Region")),
            }
        )
    if capped:
        report.warn(f"Rows above {ctx.grower_ha_cap:,.0f} ha capped", capped)
    report.accepted = len(rows)
    report.info = {
        "crops": len({r["cropLocal"] for r in rows}),
        "syngentaRows": sum(r["owner"] == "syngenta" for r in rows),
    }
    return rows, report
