"""Validators for the files that do not exist in i-MAPS today (templates live in template_files.py)."""

import re
from collections import defaultdict

import pandas as pd

from app.ingest.lookups import ImportContext
from app.ingest.reader import records, require_columns, to_float, to_int, to_text
from app.ingest.report import ImportReport

ROLES = {"admin", "lead", "rep"}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_actuals(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("actuals")
    require_columns(frame, ["country_code", "micro_segment_id", "year", "month", "sales_qty_ks"])
    rows: dict[tuple, dict] = {}
    for row_no, r in records(frame):
        report.rows_read += 1
        country = ctx.country(r.get("country_code"))
        segment_id, year, month = (
            to_int(r.get("micro_segment_id")),
            to_int(r.get("year")),
            to_int(r.get("month")),
        )
        qty = to_float(r.get("sales_qty_ks"))
        # sales_value_eur is the pre-USD header, still accepted for one release.
        value = to_float(r.get("sales_value_usd", r.get("sales_value_eur")))
        currency = (to_text(r.get("currency")) or "USD").upper()
        usd = value if value is None or currency == "USD" else ctx.fx.to_usd(value, currency, year)
        if country is None:
            report.reject(row_no, f"Unknown country '{r.get('country_code')}'")
        elif segment_id not in ctx.segment_ids:
            report.reject(
                row_no, f"Micro-segment {r.get('micro_segment_id')} is not in the product hierarchy"
            )
        elif year is None or month is None or not 1 <= month <= 12:
            report.reject(row_no, "year must be a whole number and month 1-12")
        elif qty is None or qty < 0 or (value is not None and value < 0):
            report.reject(row_no, "sales_qty_ks is required and amounts cannot be negative")
        elif value is not None and usd is None:
            report.reject(row_no, f"No budget rate for {currency} in {year}; upload the budget rates first")
        else:
            if value is not None and currency != "USD":
                report.warn(f"sales_value converted from {currency} to USD at the budget rate")
            value = usd
            key = (country, segment_id, year, month)
            if key in rows:
                report.warn("Duplicate country/micro-segment/month; the last row wins")
            if value is None:
                report.warn("Blank sales_value_usd filled from the plan net price")
            rows[key] = {
                "countryCode": country,
                "segmentId": segment_id,
                "year": year,
                "month": month,
                "qtyKs": qty,
                "valueUsd": value,
            }
    report.accepted = len(rows)
    report.info = {
        "months": sorted({f"{k[2]}-{k[3]:02d}" for k in rows}),
        "countries": sorted({k[0] for k in rows}),
    }
    return list(rows.values()), report


def validate_assignments(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("assignments")
    require_columns(frame, ["email", "name", "role"])
    users: dict[str, dict] = {}
    for row_no, r in records(frame):
        report.rows_read += 1
        email = (to_text(r.get("email")) or "").lower()
        role = (to_text(r.get("role")) or "").lower()
        if not EMAIL.match(email):
            report.reject(row_no, "A valid email is required")
            continue
        if role not in ROLES:
            report.reject(row_no, "role must be admin, lead or rep")
            continue
        user = users.setdefault(
            email, {"email": email, "name": to_text(r.get("name")) or email, "role": role, "scopes": []}
        )
        scope_type = (to_text(r.get("scope_type")) or "").lower()
        ids = [s.strip() for s in (to_text(r.get("scope_ids")) or "").split(";") if s.strip()]
        if not scope_type and not ids:
            continue
        country = ctx.country(r.get("country_code"))
        if country is None or scope_type not in ("mega", "micro") or not ids:
            report.reject(row_no, "Scopes need country_code, scope_type (mega or micro) and scope_ids")
            continue
        for scope_id in ids:
            known = (scope_type == "mega" and scope_id in ctx.mega_ids) or (
                scope_type == "micro" and to_int(scope_id) in ctx.segment_ids
            )
            if not known:
                report.warn(
                    f"Unknown {scope_type}-segment in scope_ids; kept for when the hierarchy includes it"
                )
            user["scopes"].append({"countryCode": country, "scopeType": scope_type, "scopeId": scope_id})
    reps_without_scope = sum(1 for u in users.values() if u["role"] == "rep" and not u["scopes"])
    if reps_without_scope:
        report.warn("Reps without scopes will not see any segment", reps_without_scope)
    report.accepted = len(users)
    report.info = {"roles": {role: sum(u["role"] == role for u in users.values()) for role in sorted(ROLES)}}
    return list(users.values()), report


def validate_seasonality(frame: pd.DataFrame, ctx: ImportContext) -> tuple[list[dict], ImportReport]:
    report = ImportReport("seasonality")
    require_columns(frame, ["country_code", "month", "weight"])
    weights: dict[tuple, dict[int, float]] = defaultdict(dict)
    for row_no, r in records(frame):
        report.rows_read += 1
        country = ctx.country(r.get("country_code"))
        micro, mega = to_int(r.get("micro_segment_id")), to_text(r.get("mega_segment_id"))
        month, weight = to_int(r.get("month")), to_float(r.get("weight"))
        if country is None:
            report.reject(row_no, f"Unknown country '{r.get('country_code')}'")
            continue
        if (micro is None) == (mega is None):
            report.reject(row_no, "Give exactly one of micro_segment_id or mega_segment_id")
            continue
        if month is None or not 1 <= month <= 12 or weight is None or weight < 0:
            report.reject(row_no, "month must be 1-12 and weight a non-negative number")
            continue
        key = (country, "micro", str(micro)) if micro is not None else (country, "mega", mega)
        weights[key][month] = weight
    rows = []
    for (country, scope_type, scope_id), by_month in weights.items():
        total = sum(by_month.values())
        if total <= 0:
            report.warn("A seasonality key has zero total weight and was skipped")
            continue
        if len(by_month) < 12:
            report.warn("A seasonality key is missing months; missing months get weight 0")
        for month in range(1, 13):
            rows.append(
                {
                    "countryCode": country,
                    "scopeType": scope_type,
                    "scopeId": scope_id,
                    "month": month,
                    "weight": by_month.get(month, 0.0) / total,
                }
            )
    report.accepted = len(rows)
    report.info = {"keys": len(weights)}
    return rows, report
