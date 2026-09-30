"""Read and clean the raw i-MAPS / CRM spreadsheets for the locked scope."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

SCOPE_MEGA_DESC = "SWEET PEPPER BLOCKY PGH"
SCOPE_MEGA_ID = "SP01"
YEARS = list(range(2024, 2031))
GROWER_HA_CAP = 500

FILES = {
    "market": "MV360 Market Spain Sample.xlsx",
    "sales": "MV360 Sales Spain Sample.xlsx",
    "competitors": "MV360 Competitors Spain Sample.xlsx",
    "grower": "Grower Potential ES Sample.xlsx",
    "hierarchy": "Prod Hierarchy - complete.xlsx",
    "geo": "Spain Geo.xlsx",
}

NOTE_COLUMNS = {
    "competitors": "CompetitorPOV",
    "dynamics": "MarketDynamics",
    "growers": "GrowersPOV",
    "consumers": "ConsumersPov",
    "distributors": "Distributors",
    "technology": "TechnologyAdapt",
}


@dataclass
class Report:
    sections: dict[str, dict] = field(default_factory=dict)

    def add(self, section: str, key: str, value) -> None:
        self.sections.setdefault(section, {})[key] = value


def _num(value) -> float:
    return 0.0 if pd.isna(value) else float(value)


def _text(value) -> str | None:
    if pd.isna(value):
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _normalize(value) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def load_hierarchy(raw: Path, report: Report) -> pd.DataFrame:
    sheets = pd.read_excel(raw / FILES["hierarchy"], sheet_name=None)
    report.add("hierarchy", "tabs", {name: len(df) for name, df in sheets.items()})
    ph = sheets["prod hierarchy"]
    scoped = ph[ph["f_megaSegmentDesc"] == SCOPE_MEGA_DESC]
    report.add("hierarchy", "scopeMicroSegments", int(len(scoped)))
    return scoped


def load_market(raw: Path, report: Report) -> pd.DataFrame:
    market = pd.read_excel(raw / FILES["market"])
    report.add("market", "rowsRead", int(len(market)))
    counts = market.groupby(["Micro Segment", "Year"]).size()
    dup_keys = counts[counts > 1].index
    report.add("market", "duplicatePairs", int(len(dup_keys)))
    value_cols = ["Market Planted Area (HA)", "Market Qty (KS)", "Market AvgPrice (ExSeed)"]
    dups = market.set_index(["Micro Segment", "Year"]).loc[dup_keys, value_cols]
    conflicting = dups.groupby(level=[0, 1]).nunique().gt(1).any(axis=1).sum()
    report.add("market", "conflictingDuplicatePairs", int(conflicting))
    deduped = market.sort_values("Modified").drop_duplicates(["Micro Segment", "Year"], keep="last")
    report.add("market", "rowsRemovedAsDuplicates", int(len(market) - len(deduped)))
    ratio = deduped["Market Qty (KS)"] / (
        deduped["Market Planted Area (HA)"] * deduped["Market Avg Plant Density"]
    )
    ratio = ratio.replace([float("inf")], pd.NA).dropna()
    report.add("market", "rowsWithHaAndDensity", int(len(ratio)))
    report.add("market", "qtyEqualsHaTimesDensityRows", int(((ratio - 1).abs() < 1e-3).sum()))
    return deduped[deduped["Mega Segment Desc"] == SCOPE_MEGA_DESC]


def load_sales(raw: Path, hierarchy: pd.DataFrame, report: Report) -> pd.DataFrame:
    sales = pd.read_excel(raw / FILES["sales"])
    report.add("sales", "rowsRead", int(len(sales)))
    report.add("sales", "countryNormalized", int((sales["Country"] == "SPAIN").sum()))
    sales["Country"] = "Spain"
    missing_id = sales["Microsegment ID"].isna()
    report.add("sales", "rowsWithoutMicroSegmentId", int(missing_id.sum()))
    by_desc = {
        _normalize(desc): seg_id
        for desc, seg_id in zip(hierarchy["f_microSegmentDesc"], hierarchy["f_microSegment"])
    }
    normalized = sales["Microsegment Description"].map(_normalize)
    recovered = missing_id & normalized.isin(by_desc)
    sales.loc[recovered, "Microsegment ID"] = normalized[recovered].map(by_desc)
    report.add("sales", "idsRecoveredByExactDescription", int(recovered.sum()))
    report.add("sales", "rowsDroppedWithoutId", int((missing_id & ~recovered).sum()))
    report.add("sales", "rowsWithoutQuantity", int(sales["Sales Qty"].isna().sum()))
    sales = sales.dropna(subset=["Microsegment ID"])
    sales["Microsegment ID"] = sales["Microsegment ID"].astype(int)
    sales["Year"] = sales["Title"].astype(int)
    return sales[sales["Microsegment ID"].isin(hierarchy["f_microSegment"])]


def load_competitors(raw: Path, report: Report) -> pd.DataFrame:
    comp = pd.read_excel(raw / FILES["competitors"])
    report.add("competitors", "rowsRead", int(len(comp)))
    sums = comp.groupby("Mega_Segment_Id")["2026%"].sum()
    report.add("competitors", "megaSegmentsSummingTo100", int((sums.round() == 100).sum()))
    report.add("competitors", "megaSegments", int(len(sums)))
    return comp[comp["Mega_Segment_Id"] == SCOPE_MEGA_ID]


def load_grower(raw: Path, report: Report) -> pd.DataFrame:
    grower = pd.read_excel(raw / FILES["grower"])
    report.add("grower", "rowsRead", int(len(grower)))
    report.add(
        "grower",
        "countryPicklistMismatch",
        int((grower["Country Picklist"] != "ES").sum()),
    )
    report.add("grower", "regionMissingPct", round(float(grower["Region"].isna().mean()) * 100, 1))
    empty = [c for c in grower.columns if grower[c].isna().all()]
    report.add("grower", "emptyColumns", empty)
    scoped = grower[grower["Crop Local"] == SCOPE_MEGA_DESC].copy()
    report.add("grower", "scopeRows", int(len(scoped)))
    raw_total = float(scoped["Hecatres Info."].sum())
    over = scoped["Hecatres Info."] > GROWER_HA_CAP
    report.add("grower", "scopeRowsCapped", int(over.sum()))
    scoped["hectares"] = scoped["Hecatres Info."].clip(upper=GROWER_HA_CAP).astype(float)
    report.add("grower", "scopeHectaresRaw", round(raw_total))
    report.add("grower", "scopeHectaresCapped", round(float(scoped["hectares"].sum())))
    return scoped


def load_geo(raw: Path, report: Report) -> None:
    sheets = pd.read_excel(raw / FILES["geo"], sheet_name=None, dtype=str)
    city = sheets["City"]
    subtotal = city["State"].fillna("").str.endswith(" Total")
    report.add("geo", "cityRows", int(len(city)))
    report.add("geo", "subtotalRows", int(subtotal.sum()))
    report.add("geo", "provincesOrRegions", int(city.loc[~subtotal, "State"].dropna().nunique()))
    postcodes = sheets["Pincode"]["Address (Postal Code)"].dropna()
    report.add("geo", "postcodesMissingLeadingZero", int((postcodes.str.len() == 4).sum()))


def market_notes(row: pd.Series) -> dict[str, str | None]:
    return {key: _text(row.get(col)) for key, col in NOTE_COLUMNS.items()}


__all__ = [
    "FILES",
    "GROWER_HA_CAP",
    "Report",
    "SCOPE_MEGA_DESC",
    "SCOPE_MEGA_ID",
    "YEARS",
    "_num",
    "_text",
    "file_md5",
    "load_competitors",
    "load_geo",
    "load_grower",
    "load_hierarchy",
    "load_market",
    "load_sales",
    "market_notes",
]
