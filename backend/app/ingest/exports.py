"""Validators for the i-MAPS exports that carry market size, the Syngenta plan and the product hierarchy."""

from datetime import datetime

import pandas as pd

from app.ingest.lookups import ImportContext, normalize
from app.ingest.profile import profile_for
from app.ingest.reader import records, require_columns, to_datetime, to_float, to_int, to_text
from app.ingest.report import ImportReport

NOTE_COLUMNS = {
    "competitors": "CompetitorPOV",
    "dynamics": "MarketDynamics",
    "growers": "GrowersPOV",
    "consumers": "ConsumersPov",
    "distributors": "Distributors",
    "technology": "TechnologyAdapt",
}
QTY_TOLERANCE = 0.01
# Preview warns when the export's Avg Net Price and Sales Value / Sales Qty disagree by more than this.
PRICE_MISMATCH = 0.05


def validate_hierarchy(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("hierarchy")
    require_columns(
        frame, ["f_specie", "f_megaSegment", "f_megaSegmentDesc", "f_microSegment", "f_microSegmentDesc"]
    )
    rows: dict[int, dict] = {}
    for row_no, r in records(frame):
        report.rows_read += 1
        segment_id = to_int(r.get("f_microSegment"))
        description = to_text(r.get("f_microSegmentDesc"))
        mega = to_text(r.get("f_megaSegment"))
        if segment_id is None or not description or not mega:
            report.reject(row_no, "f_microSegment, f_microSegmentDesc and f_megaSegment are required")
            continue
        if segment_id in rows:
            report.warn("Duplicate micro-segment id; the last row wins")
        rows[segment_id] = {
            "id": segment_id,
            "description": description,
            "species": to_text(r.get("f_specie")),
            "megaSegmentId": mega,
            "megaSegmentDesc": to_text(r.get("f_megaSegmentDesc")) or mega,
            "cycle": to_text(r.get("Cycle")),
            "color": to_text(r.get("Color")),
            "ecology": to_text(r.get("Ecology Desc")),
            "profile": profile_for(description),
        }
    report.accepted = len(rows)
    report.info = {
        "species": len({r["species"] for r in rows.values()}),
        "megaSegments": len({r["megaSegmentId"] for r in rows.values()}),
    }
    return list(rows.values()), report


def validate_market(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("market")
    required = [
        "Country",
        "Micro Segment",
        "Year",
        "Market Planted Area (HA)",
        "Market Qty (KS)",
        "Market Avg Plant Density",
        "Market AvgPrice (ExSeed)",
    ]
    require_columns(frame, required)
    kept: dict[tuple, tuple[datetime | None, dict]] = {}
    duplicates = conflicting = 0
    for row_no, r in records(frame):
        report.rows_read += 1
        country = ctx.country(r.get("Country"))
        segment_id = to_int(r.get("Micro Segment"))
        year = to_int(r.get("Year"))
        if country is None:
            report.reject(row_no, f"Unknown country '{r.get('Country')}'")
            continue
        if segment_id is None or year is None:
            report.reject(row_no, "Micro Segment and Year must be whole numbers")
            continue
        if segment_id not in ctx.segment_ids:
            report.reject(
                row_no, f"Micro-segment {segment_id} is not in the product hierarchy (upload it first)"
            )
            continue
        values = {}
        for key, column in (
            ("hectares", "Market Planted Area (HA)"),
            ("qtyKs", "Market Qty (KS)"),
            ("density", "Market Avg Plant Density"),
            ("priceExseed", "Market AvgPrice (ExSeed)"),
            ("priceFarmgate", "Market AvgPrice (Farmgate)"),
        ):
            number = to_float(r.get(column))
            if number is not None and number < 0:
                report.reject(row_no, f"{column} is negative")
                break
            if number is None and column in required:
                report.warn(f"Blank {column} treated as 0")
            values[key] = number or 0.0
        else:
            if values["hectares"] > 0 and values["density"] > 0 and values["qtyKs"] > 0:
                expected = values["hectares"] * values["density"]
                if abs(values["qtyKs"] - expected) / expected > QTY_TOLERANCE:
                    report.warn("Market Qty (KS) differs from hectares x density by more than 1%")
            row = {
                "countryCode": country,
                "segmentId": segment_id,
                "year": year,
                **values,
                "notes": {k: to_text(r.get(c)) for k, c in NOTE_COLUMNS.items()},
            }
            key = (country, segment_id, year)
            modified = to_datetime(r.get("Modified"))
            if key in kept:
                duplicates += 1
                previous = kept[key][1]
                if any(previous[k] != row[k] for k in ("hectares", "qtyKs", "priceExseed")):
                    conflicting += 1
                previous_modified = kept[key][0]
                if previous_modified is not None and (modified is None or modified < previous_modified):
                    continue
            kept[key] = (modified, row)
    if duplicates:
        report.warn(
            "Duplicate country/micro-segment/year rows; the most recently modified row wins", duplicates
        )
    rows = [row for _, row in kept.values()]
    report.accepted = len(rows)
    report.info = {
        "countries": sorted({r["countryCode"] for r in rows}),
        "years": sorted({r["year"] for r in rows}),
        "conflictingDuplicates": conflicting,
    }
    return rows, report


def validate_plan(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("plan")
    require_columns(frame, ["Title", "Country", "Microsegment ID", "Sales Qty", "Sales Value"])
    grouped: dict[tuple, dict] = {}
    recovered = 0
    for row_no, r in records(frame):
        report.rows_read += 1
        country = ctx.country(r.get("Country"))
        year = to_int(r.get("Title"))
        segment_id = to_int(r.get("Microsegment ID"))
        if segment_id is None and to_text(r.get("Microsegment Description")):
            segment_id = ctx.segment_by_desc.get(normalize(r["Microsegment Description"]))
            recovered += segment_id is not None
        if country is None:
            report.reject(row_no, f"Unknown country '{r.get('Country')}'")
            continue
        if year is None:
            report.reject(row_no, "Title must hold the year")
            continue
        if segment_id is None:
            report.reject(row_no, "No Microsegment ID and the description does not match the hierarchy")
            continue
        if segment_id not in ctx.segment_ids:
            report.reject(
                row_no, f"Micro-segment {segment_id} is not in the product hierarchy (upload it first)"
            )
            continue
        qty, value = to_float(r.get("Sales Qty")), to_float(r.get("Sales Value"))
        if qty is None:
            report.warn("Blank Sales Qty treated as 0")
        if (qty or 0) < 0 or (value or 0) < 0:
            report.reject(row_no, "Sales Qty and Sales Value cannot be negative")
            continue
        currency = to_text(r.get("Currency"))
        if value is not None and currency and currency.upper() != "USD":
            converted = ctx.fx.to_usd(value, currency, year)
            if converted is None:
                report.reject(row_no, f"No budget rate for {currency.upper()} in {year}; upload the budget rates first")
                continue
            report.warn(f"Sales Value converted from {currency.upper()} to USD at the budget rate")
            value = converted
        avg_price = to_float(r.get("Avg Net Price"))
        key = (country, segment_id, year)
        row = grouped.setdefault(
            key,
            {
                "countryCode": country,
                "segmentId": segment_id,
                "year": year,
                "qtyKs": 0.0,
                "valueUsd": 0.0,
                "fpiQtyKs": 0.0,
                "comment": None,
                "_avgPriceQty": 0.0,
            },
        )
        if row["qtyKs"] or row["valueUsd"]:
            report.warn("Several rows for the same country/micro-segment/year were summed")
        row["qtyKs"] += qty or 0.0
        row["valueUsd"] += value or 0.0
        if avg_price is not None and qty:
            row["_avgPriceQty"] += avg_price * qty
        row["fpiQtyKs"] += to_float(r.get("FPI Qty")) or 0.0
        row["comment"] = row["comment"] or to_text(r.get("Qualitative Comments"))
    rows = list(grouped.values())
    mismatched = []
    for row in rows:
        computed = row["valueUsd"] / row["qtyKs"] if row["qtyKs"] else 0.0
        stated = row.pop("_avgPriceQty") / row["qtyKs"] if row["qtyKs"] else 0.0
        if stated and computed and abs(stated - computed) / computed > PRICE_MISMATCH:
            mismatched.append(f"{row['countryCode']} {row['segmentId']} {row['year']}")
        use_stated = ctx.price_source == "avg_net_price" and stated > 0
        row["netPrice"] = round(stated if use_stated else computed, 4)
    if mismatched:
        report.warn(
            f"Avg Net Price differs from Sales Value / Sales Qty by more than {PRICE_MISMATCH:.0%}", len(mismatched)
        )
    planning_year = ctx.current_year
    report.accepted = len(rows)
    report.info = {
        "countries": sorted({r["countryCode"] for r in rows}),
        "years": sorted({r["year"] for r in rows}),
        "idsRecoveredFromDescription": recovered,
        "priceSource": ctx.price_source,
        "priceMismatches": mismatched[:20],
        **(
            {
                "actualYears": sorted({r["year"] for r in rows if r["year"] < planning_year}),
                "planYears": sorted({r["year"] for r in rows if r["year"] >= planning_year}),
            }
            if planning_year
            else {}
        ),
    }
    return rows, report
