"""Downloadable CSV templates for every upload kind.

Export-based kinds use the exact i-MAPS / CRM column names, so an admin can either upload the export as-is or
fill the template by hand. Example rows are internally consistent (market qty = hectares x density) and pass
their own validator (see tests/test_ingest_templates.py).
"""

import csv
import io

HIERARCHY = (
    [
        "f_specie",
        "f_megaSegment",
        "f_megaSegmentDesc",
        "f_microSegment",
        "f_microSegmentDesc",
        "Cycle",
        "Color",
        "Ecology Desc",
    ],
    [
        [
            "PEPPER SWEET",
            "SP01",
            "SWEET PEPPER BLOCKY PGH",
            "2481",
            "PEP-SWEET BLOCKY-AUTUMN-MEDIUM-WARM to COOL-PGH-RED-FRESH",
            "WARM TO COOL",
            "RED",
            "PASSIVE GREENHOUSE",
        ],
        [
            "PEPPER SWEET",
            "SP01",
            "SWEET PEPPER BLOCKY PGH",
            "2482",
            "PEP-SWEET BLOCKY-AUTUMN-LATE-WARM to COOL-PGH-RED-FRESH",
            "WARM TO COOL",
            "RED",
            "PASSIVE GREENHOUSE",
        ],
        [
            "PEPPER SWEET",
            "SP01",
            "SWEET PEPPER BLOCKY PGH",
            "2432",
            "PEP-SWEET BLOCKY-SPRING-COOL to WARM-PGH-RED-FRESH",
            "COOL TO WARM",
            "RED",
            "PASSIVE GREENHOUSE",
        ],
    ],
)

MARKET = (
    [
        "Country",
        "Micro Segment",
        "Year",
        "Market Planted Area (HA)",
        "Market Qty (KS)",
        "Market Avg Plant Density",
        "Market AvgPrice (ExSeed)",
        "Market AvgPrice (Farmgate)",
        "CompetitorPOV",
        "MarketDynamics",
        "GrowersPOV",
        "ConsumersPov",
        "Distributors",
        "TechnologyAdapt",
        "Modified",
    ],
    [
        [
            "Spain",
            "2482",
            "2025",
            "3000",
            "63000",
            "21",
            "410",
            "470",
            "Sur Seeds and Clause lead",
            "Late cycle stable",
            "",
            "",
            "",
            "",
            "2026-02-01 10:00",
        ],
        [
            "Spain",
            "2482",
            "2026",
            "3300",
            "69300",
            "21",
            "420",
            "480",
            "Sur Seeds and Clause lead",
            "T. parvispinus pressure on early cycles",
            "",
            "",
            "",
            "",
            "2026-03-01 10:00",
        ],
        [
            "Spain",
            "2432",
            "2026",
            "1350",
            "33750",
            "25",
            "382",
            "441",
            "",
            "",
            "",
            "",
            "",
            "",
            "2026-02-01 10:00",
        ],
    ],
)

PLAN = (
    [
        "Title",
        "Country",
        "Microsegment ID",
        "Microsegment Description",
        "Sales Qty",
        "Sales Value",
        "FPI Qty",
        "Qualitative Comments",
    ],
    [
        ["2025", "Spain", "2482", "", "46000", "19600000", "", "Leader of the red blocky segment"],
        ["2026", "Spain", "2482", "", "45000", "20250000", "", "Leader of the red blocky segment"],
        [
            "2026",
            "Spain",
            "",
            "PEP-SWEET BLOCKY-SPRING-COOL to WARM-PGH-RED-FRESH",
            "7000",
            "2702000",
            "",
            "ID left blank: recovered from the description",
        ],
    ],
)

COMPETITORS = (
    [
        "Forecast Customer Country_D",
        "Mega_Segment_Id",
        "CompetitorDesc",
        "2025",
        "2026",
        "2025%",
        "2026%",
        "CompetitorTrend",
    ],
    [
        ["Spain", "SP01", "Syngenta", "", "", "31", "30", "Growing"],
        ["Spain", "SP01", "Limagrain", "", "", "22", "23", "Growing"],
        ["Spain", "SP01", "Sur Seeds", "", "", "14", "15", "Growing"],
        ["Spain", "SP01", "Others", "", "", "33", "32", "Declining"],
    ],
)

GROWER = (
    ["Country Name", "Crop Local", "Variety", "Competitor", "Hecatres Info.", "Density", "Region"],
    [
        ["Spain", "SWEET PEPPER BLOCKY PGH", "LEONTES", "SYNGENTA", "120", "21", "Med-Sur Almeria-Costas"],
        ["Spain", "SWEET PEPPER BLOCKY PGH", "HOKKAIDO", "SYNGENTA", "45", "21", ""],
        ["Spain", "SWEET PEPPER BLOCKY PGH", "OTHER VARIETY", "Rijk Zwaan", "30", "21", "Murcia"],
    ],
)

ACTUALS = (
    ["country_code", "micro_segment_id", "year", "month", "sales_qty_ks", "sales_value_usd"],
    [["ES", "2482", "2026", "9", "13250", "5994000"], ["ES", "2432", "2026", "9", "1180", ""]],
)

ASSIGNMENTS = (
    ["email", "name", "role", "country_code", "scope_type", "scope_ids"],
    [
        ["ana.rep@example.com", "Ana Rep", "rep", "ES", "micro", "2481;2482"],
        ["lead@example.com", "Consensus Lead", "lead", "ES", "mega", "SP01"],
        ["admin@example.com", "Data Admin", "admin", "", "", ""],
    ],
)

SEASONALITY = (
    ["country_code", "micro_segment_id", "mega_segment_id", "month", "weight"],
    [
        ["ES", "", "SP01", str(m), w]
        for m, w in zip(range(1, 13), ["2", "2", "2", "3", "6", "12", "18", "22", "18", "8", "4", "3"])
    ],
)

BUDGET_RATES = (
    ["budget_year", "currency", "currency_name", "per_usd"],
    [
        ["2026", "USD", "US Dollar", "1"],
        ["2026", "EUR", "Euro", "0.85"],
        ["2026", "GBP", "Pound Sterling", "0.73"],
        ["2026", "MXN", "Mexican Peso", "18.9"],
    ],
)

SAC_SALES = (
    [
        "country_code",
        "micro_segment_id",
        "variety",
        "year",
        "month",
        "measure",
        "qty_ks",
        "net_sales_usd",
        "snapshot",
        "planner_email",
        "currency",
    ],
    [
        ["ES", "2482", "Leontes", "2026", "9", "Actual", "9100", "4095000", "", "", "USD"],
        ["ES", "2482", "Hokkaido", "2026", "9", "Actual", "4150", "1867500", "", "", "USD"],
        ["ES", "2482", "Leontes", "2026", "10", "Forecast", "2600", "1170000", "2026-09-28", "ana.rep@example.com", "USD"],
        ["ES", "2482", "Hokkaido", "2026", "10", "Forecast", "1300", "585000", "2026-09-28", "ana.rep@example.com", "USD"],
    ],
)

VARIETY_MAP = (
    ["country_code", "variety", "micro_segment_id"],
    [["ES", "Leontes", "2482"], ["ES", "Hokkaido", "2482"], ["ES", "Bokken", "2481"]],
)

TEMPLATES: dict[str, tuple[list[str], list[list[str]]]] = {
    "hierarchy": HIERARCHY,
    "market": MARKET,
    "plan": PLAN,
    "competitors": COMPETITORS,
    "actuals": ACTUALS,
    "assignments": ASSIGNMENTS,
    "grower": GROWER,
    "seasonality": SEASONALITY,
    "budget_rates": BUDGET_RATES,
    "variety_map": VARIETY_MAP,
    "sac_sales": SAC_SALES,
}


def template_csv(kind: str) -> str:
    header, rows = TEMPLATES[kind]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()
