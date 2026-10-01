import json
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AppSetting,
    ChatAction,
    Claim,
    CompetitorShare,
    Country,
    DemandEntry,
    DemoClock,
    EntryNote,
    FxRate,
    GrowerPotential,
    IbpForecast,
    LeadRule,
    MarketYear,
    MonthlyActual,
    MonthlyPlan,
    PlanYear,
    RepTrackRecord,
    Seasonality,
    Segment,
    VarietyMap,
)
from app.services.cube_builder import Reference

DEMO_COUNTRY = "ES"
DEMO_CROP_LOCAL = "SWEET PEPPER BLOCKY PGH"

SIGNAL_BY_DRIVER = {
    "competitor_move": "competitor_share",
    "area_change": "market_hectares",
    "pest_disease": "market_hectares",
    "weather_water": "market_hectares",
}


def signal_for(driver: str) -> str:
    return SIGNAL_BY_DRIVER.get(driver, "next_month_actuals")


def read_seed(seed_dir: Path, name: str) -> list | dict:
    return json.loads((seed_dir / f"{name}.json").read_text())


def reference_from_seed(seed_dir: Path) -> Reference:
    def rows(name: str) -> list[dict]:
        return read_seed(seed_dir, name)  # type: ignore[return-value]

    return Reference(
        segments=[
            Segment(
                id=s["id"],
                description=s["description"],
                species=s.get("species"),
                cycle=s["cycle"],
                color=s["color"],
                ecology=s["ecology"],
                mega_segment_id=s["megaSegmentId"],
                mega_segment_desc=s["megaSegmentDesc"],
                profile=s["profile"],
                owner_id=s["ownerId"],
            )
            for s in rows("segments")
        ],
        market=[
            MarketYear(
                country_code=m.get("countryCode", DEMO_COUNTRY),
                segment_id=m["segmentId"],
                year=m["year"],
                hectares=m["hectares"],
                qty_ks=m["qtyKs"],
                density=m["density"],
                price_exseed=m["priceExseed"],
                price_farmgate=m["priceFarmgate"],
                notes=m["notes"],
            )
            for m in rows("market_years")
        ],
        plan=[
            PlanYear(
                country_code=p.get("countryCode", DEMO_COUNTRY),
                segment_id=p["segmentId"],
                year=p["year"],
                qty_ks=p["qtyKs"],
                value_usd=p["valueUsd"],
                net_price=p["netPrice"],
                fpi_qty_ks=p["fpiQtyKs"],
                comment=p["comment"],
            )
            for p in rows("plan_years")
        ],
        monthly_plan=[
            MonthlyPlan(
                country_code=r.get("countryCode", DEMO_COUNTRY),
                segment_id=r["segmentId"],
                year=r["year"],
                month=r["month"],
                qty_ks=r["qtyKs"],
                basis="synthetic",
            )
            for r in rows("monthly_plan")
        ],
        monthly_actuals=[
            MonthlyActual(
                country_code=r.get("countryCode", DEMO_COUNTRY),
                segment_id=r["segmentId"],
                year=r["year"],
                month=r["month"],
                qty_ks=r["qtyKs"],
                value_usd=r["valueUsd"],
            )
            for r in rows("monthly_actuals")
        ],
        competitors=[
            CompetitorShare(
                country_code=c.get("countryCode", DEMO_COUNTRY),
                mega_segment_id=c["megaSegmentId"],
                competitor=c["competitor"],
                year=c["year"],
                share_pct=c["sharePct"],
                value_usd=c["valueUsd"],
                trend=c["trend"],
            )
            for c in rows("competitor_shares")
        ],
        grower=[
            GrowerPotential(
                country_code=g.get("countryCode", DEMO_COUNTRY),
                crop_local=g.get("cropLocal", DEMO_CROP_LOCAL),
                variety=g["variety"],
                owner=g["owner"],
                hectares=g["hectares"],
                density=g["density"],
                region=g["region"],
            )
            for g in rows("grower_potential")
        ],
    )


def _history_rows(seed_dir: Path) -> list[tuple[DemandEntry, Claim]]:
    out = []
    for h in read_seed(seed_dir, "history_entries"):
        entry = DemandEntry(
            user_id=h["userId"],
            country_code=DEMO_COUNTRY,
            segment_id=h["segmentId"],
            year=h["year"],
            month=h["month"],
            value=h["value"],
            low=h["low"],
            high=h["high"],
            justification=h["justification"],
            flags=[],
            status="approved",
            source="history",
        )
        c = h["claim"]
        claim = Claim(
            driver=c["driver"],
            direction=c["direction"],
            competitor=c["competitor"],
            variety=c["variety"],
            evidence_source=c["evidenceSource"],
            decisions={},
            provider="history",
            signal=signal_for(c["driver"]),
            check_year=h["year"],
            check_month=h["month"],
            resolution=h["resolution"],
        )
        out.append((entry, claim))
    return out


async def seed_database(db: AsyncSession, seed_dir: Path) -> None:
    from app.services.track_record_service import recompute_track_records

    for model in (
        AppSetting,
        Seasonality,
        ChatAction,
        EntryNote,
        LeadRule,
        Claim,
        DemandEntry,
        RepTrackRecord,
        DemoClock,
        FxRate,
        IbpForecast,
        VarietyMap,
        MonthlyActual,
        MonthlyPlan,
        PlanYear,
        MarketYear,
        CompetitorShare,
        GrowerPotential,
        Segment,
    ):
        await db.execute(delete(model))

    ref = reference_from_seed(seed_dir)
    db.add_all(ref.segments)
    await db.flush()
    for group in (ref.market, ref.plan, ref.monthly_plan, ref.monthly_actuals, ref.competitors, ref.grower):
        db.add_all(group)

    meta = read_seed(seed_dir, "meta")
    db.add(DemoClock(id=1, year=meta["currentYear"], month=meta["clockStartMonth"]))
    if await db.get(Country, DEMO_COUNTRY) is None:
        db.add(Country(code=DEMO_COUNTRY, name=meta["country"], aliases=[meta["country"].upper()], currency="EUR"))
    # Synthetic IBP snapshot: reference only until an admin switches the demand source to IBP.
    if (seed_dir / "ibp_forecasts.json").exists():
        db.add_all(
            IbpForecast(
                country_code=DEMO_COUNTRY,
                segment_id=f["segmentId"],
                variety=f["variety"],
                year=f["year"],
                month=f["month"],
                snapshot=f["snapshot"],
                qty_ks=f["qtyKs"],
                value_usd=f.get("valueUsd"),
                planner_id=f.get("plannerId"),
            )
            for f in read_seed(seed_dir, "ibp_forecasts")
        )
    # Rounded demo rates, not the finance file (that one is internal and stays in data/raw/).
    if (seed_dir / "budget_rates.json").exists():
        db.add_all(
            FxRate(
                budget_year=r["budgetYear"],
                currency=r["currency"],
                currency_name=r["currencyName"],
                per_usd=r["perUsd"],
            )
            for r in read_seed(seed_dir, "budget_rates")
        )

    for entry, claim in _history_rows(seed_dir):
        db.add(entry)
        await db.flush()
        claim.entry_id = entry.id
        db.add(claim)
    await db.flush()
    await recompute_track_records(db)
    await db.commit()
