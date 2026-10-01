"""Build anonymized seed JSON for the locked scope from data/raw/*.xlsx.

Run from backend/: `uv run python ../scripts/ingest/build_seed.py`
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from load import (  # noqa: E402
    FILES,
    GROWER_HA_CAP,
    SCOPE_MEGA_DESC,
    SCOPE_MEGA_ID,
    YEARS,
    Report,
    _num,
    _text,
    file_md5,
    load_competitors,
    load_geo,
    load_grower,
    load_hierarchy,
    load_market,
    load_sales,
    market_notes,
)
from synth import (  # noqa: E402
    ACTUAL_DRIFT_2026,
    CLOCK_START_MONTH,
    CURRENT_YEAR,
    OWNERS,
    SEED,
    Anonymizer,
    curve,
    history_entries,
    noisy_months,
    profile_for,
    split_months,
)

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
OUT = REPO / "data" / "seed"


def owner_of(segment_id: int) -> str:
    return next(rep for rep, ids in OWNERS.items() if segment_id in ids)


def build_segments(hierarchy: pd.DataFrame, market: pd.DataFrame, report: Report) -> list[dict]:
    active_ids = set(
        market[(market["Year"] == CURRENT_YEAR) & (market["Market Planted Area (HA)"] > 0)][
            "Micro Segment"
        ]
    )
    report.add("scope", "activeMicroSegments", sorted(int(i) for i in active_ids))
    report.add(
        "scope",
        "inactiveMicroSegments",
        sorted(int(i) for i in set(hierarchy["f_microSegment"]) - active_ids),
    )
    segments = []
    for _, row in hierarchy[hierarchy["f_microSegment"].isin(active_ids)].iterrows():
        segment_id = int(row["f_microSegment"])
        description = str(row["f_microSegmentDesc"])
        segments.append(
            {
                "id": segment_id,
                "description": description,
                "cycle": _text(row["Cycle"]),
                "color": _text(row["Color"]),
                "ecology": _text(row["Ecology Desc"]),
                "megaSegmentId": SCOPE_MEGA_ID,
                "megaSegmentDesc": SCOPE_MEGA_DESC,
                "species": _text(row["f_specie"]),
                "profile": profile_for(description),
                "ownerId": owner_of(segment_id),
            }
        )
    return sorted(segments, key=lambda s: s["id"])


def build_market(market: pd.DataFrame, segment_ids: set[int]) -> list[dict]:
    rows = []
    for _, row in market[market["Micro Segment"].isin(segment_ids)].iterrows():
        rows.append(
            {
                "segmentId": int(row["Micro Segment"]),
                "year": int(row["Year"]),
                "hectares": _num(row["Market Planted Area (HA)"]),
                "qtyKs": _num(row["Market Qty (KS)"]),
                "density": _num(row["Market Avg Plant Density"]),
                "priceExseed": _num(row["Market AvgPrice (ExSeed)"]),
                "priceFarmgate": _num(row["Market AvgPrice (Farmgate)"]),
                "notes": market_notes(row),
            }
        )
    return rows


def build_plan(sales: pd.DataFrame, segment_ids: set[int], anon: Anonymizer) -> list[dict]:
    grouped = (
        sales[sales["Microsegment ID"].isin(segment_ids)]
        .groupby(["Microsegment ID", "Year"])
        .agg(
            qty=("Sales Qty", "sum"),
            value=("Sales Value", "sum"),
            fpi=("FPI Qty", "sum"),
            comment=("Qualitative Comments", "first"),
        )
        .reset_index()
    )
    rows = []
    for _, row in grouped.iterrows():
        qty, value = anon.scale(_num(row["qty"]), _num(row["value"]))
        rows.append(
            {
                "segmentId": int(row["Microsegment ID"]),
                "year": int(row["Year"]),
                "qtyKs": qty,
                "valueUsd": value,
                "netPrice": round(value / qty, 2) if qty else 0.0,
                "fpiQtyKs": _num(row["fpi"]),
                "comment": _text(row["comment"]),
            }
        )
    return rows


def build_competitors(comp: pd.DataFrame, plan: list[dict], market: list[dict]) -> list[dict]:
    rows = []
    for year in YEARS:
        market_value = sum(m["qtyKs"] * m["priceExseed"] for m in market if m["year"] == year)
        syn_value = sum(p["valueUsd"] for p in plan if p["year"] == year)
        syn_pct = round(100 * syn_value / market_value, 1) if market_value else 0.0
        others = comp[comp["CompetitorDesc"] != "Syngenta"]
        other_total = float(others[f"{year}%"].sum()) or 1.0
        rows.append(
            {
                "megaSegmentId": SCOPE_MEGA_ID,
                "competitor": "Syngenta",
                "year": year,
                "sharePct": syn_pct,
                "valueUsd": round(syn_value, 2),
                "trend": _text(comp[comp["CompetitorDesc"] == "Syngenta"]["CompetitorTrend"].iloc[0]),
            }
        )
        for _, row in others.iterrows():
            pct = round(float(row[f"{year}%"]) * (100 - syn_pct) / other_total, 1)
            rows.append(
                {
                    "megaSegmentId": SCOPE_MEGA_ID,
                    "competitor": str(row["CompetitorDesc"]),
                    "year": year,
                    "sharePct": pct,
                    "valueUsd": round(market_value * pct / 100, 2),
                    "trend": _text(row["CompetitorTrend"]),
                }
            )
    return rows


def build_monthly(
    rng: np.random.Generator, segments: list[dict], plan: list[dict]
) -> tuple[list[dict], list[dict], dict[int, list[float]], dict[int, list[float]]]:
    plan_rows, actual_rows = [], []
    plan_2026: dict[int, list[float]] = {}
    actual_2026: dict[int, list[float]] = {}
    for seg in segments:
        weights = curve(seg["profile"])
        for year in (CURRENT_YEAR - 1, CURRENT_YEAR):
            yearly = next(
                (p for p in plan if p["segmentId"] == seg["id"] and p["year"] == year), None
            )
            total = yearly["qtyKs"] if yearly else 0.0
            price = yearly["netPrice"] if yearly else 0.0
            months_plan = split_months(total, weights)
            drift = ACTUAL_DRIFT_2026.get(seg["id"], 0.0) if year == CURRENT_YEAR else 0.0
            months_actual = noisy_months(rng, months_plan, drift, 0.06)
            if year == CURRENT_YEAR - 1 and sum(months_actual):
                observed = sum(months_actual)
                months_actual = split_months(total, [a / observed for a in months_actual])
            else:
                plan_2026[seg["id"]] = months_plan
                actual_2026[seg["id"]] = months_actual
            for month in range(1, 13):
                plan_rows.append(
                    {"segmentId": seg["id"], "year": year, "month": month,
                     "qtyKs": months_plan[month - 1]}
                )
                qty = months_actual[month - 1]
                actual_rows.append(
                    {
                        "segmentId": seg["id"],
                        "year": year,
                        "month": month,
                        "qtyKs": qty,
                        "valueUsd": round(qty * price * (1 + float(rng.normal(0, 0.01))), 2),
                    }
                )
    return plan_rows, actual_rows, plan_2026, actual_2026


def build_grower(grower: pd.DataFrame) -> list[dict]:
    return [
        {
            "variety": _text(row["Variety"]),
            "owner": "syngenta" if row["Competitor"] == "SYNGENTA" else "unknown",
            "hectares": float(row["hectares"]),
            "density": _num(row["Density"]),
            "region": _text(row["Region"]),
        }
        for _, row in grower.iterrows()
    ]


def write(name: str, payload) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    report = Report()

    sales_copy = RAW.parent.parent.parent / "Downloads" / "MV360 Sales Spain Sample (1).xlsx"
    if sales_copy.exists():
        same = file_md5(sales_copy) == file_md5(RAW / FILES["sales"])
        report.add("sales", "secondCopyIdentical", same)

    hierarchy = load_hierarchy(RAW, report)
    market_df = load_market(RAW, report)
    sales_df = load_sales(RAW, hierarchy, report)
    comp_df = load_competitors(RAW, report)
    grower_df = load_grower(RAW, report)
    load_geo(RAW, report)

    segments = build_segments(hierarchy, market_df, report)
    ids = {s["id"] for s in segments}
    market = build_market(market_df, ids)
    plan = build_plan(sales_df, ids, Anonymizer(rng))
    competitors = build_competitors(comp_df, plan, market)
    monthly_plan, monthly_actuals, plan_2026, actual_2026 = build_monthly(rng, segments, plan)

    zero_market = sorted(
        {p["segmentId"] for p in plan if p["qtyKs"] > 0}
        - {m["segmentId"] for m in market if m["qtyKs"] > 0}
    )
    report.add("scope", "segmentsWithSalesButNoMarket", zero_market)
    report.add("scope", "growerHaCap", GROWER_HA_CAP)
    report.add("anonymization", "method", "hidden scale factor + 3% per-row noise")
    report.add("anonymization", "repNames", "pseudonymized (Rep A, Rep B)")
    report.add("synthetic", "monthlySplit", "seasonal curve per cycle profile (to confirm)")
    report.add("synthetic", "clockStart", f"{CURRENT_YEAR}-{CLOCK_START_MONTH:02d}")

    write("segments", segments)
    write("market_years", market)
    write("plan_years", plan)
    write("competitor_shares", competitors)
    write("monthly_plan", monthly_plan)
    write("monthly_actuals", monthly_actuals)
    write("grower_potential", build_grower(grower_df))
    write("history_entries", history_entries(rng, plan_2026, actual_2026))
    write(
        "meta",
        {
            "country": "Spain",
            "species": "Sweet Pepper",
            "megaSegmentId": SCOPE_MEGA_ID,
            "megaSegmentDesc": SCOPE_MEGA_DESC,
            "currentYear": CURRENT_YEAR,
            "clockStartMonth": CLOCK_START_MONTH,
        },
    )
    write("ingest_report", report.sections)
    print(f"Wrote {len(segments)} segments, {len(plan)} plan rows to {OUT}")


if __name__ == "__main__":
    main()
