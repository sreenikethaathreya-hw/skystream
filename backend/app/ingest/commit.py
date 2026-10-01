"""Write validated rows into the domain tables. Each kind replaces what it covers and leaves the rest."""

from collections import defaultdict

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CompetitorShare,
    FxRate,
    GrowerPotential,
    IbpForecast,
    MarketYear,
    MonthlyActual,
    PlanYear,
    Seasonality,
    Segment,
    VarietyMap,
)
from app.schemas.api import ScopeIn
from app.services.user_service import upsert_user

CHUNK = 500


def _chunks(values: list) -> list[list]:
    return [values[i : i + CHUNK] for i in range(0, len(values), CHUNK)]


async def _replace_yearly(db: AsyncSession, model, rows: list[dict], build) -> int:
    by_country_year: dict[tuple[str, int], list[int]] = defaultdict(list)
    for r in rows:
        by_country_year[(r["countryCode"], r["year"])].append(r["segmentId"])
    for (country, year), segment_ids in by_country_year.items():
        for chunk in _chunks(sorted(set(segment_ids))):
            await db.execute(
                delete(model).where(
                    model.country_code == country, model.year == year, model.segment_id.in_(chunk)
                )
            )
    db.add_all(build(r) for r in rows)
    return len(rows)


async def commit_hierarchy(db: AsyncSession, rows: list[dict]) -> dict:
    existing = {s.id: s for s in (await db.execute(select(Segment))).scalars()}
    created = 0
    for r in rows:
        segment = existing.get(r["id"])
        if segment is None:
            segment = Segment(id=r["id"])
            db.add(segment)
            created += 1
        segment.description, segment.species = r["description"], r["species"]
        segment.mega_segment_id, segment.mega_segment_desc = r["megaSegmentId"], r["megaSegmentDesc"]
        segment.cycle, segment.color, segment.ecology, segment.profile = (
            r["cycle"],
            r["color"],
            r["ecology"],
            r["profile"],
        )
    return {"created": created, "updated": len(rows) - created}


async def commit_market(db: AsyncSession, rows: list[dict]) -> dict:
    count = await _replace_yearly(
        db,
        MarketYear,
        rows,
        lambda r: MarketYear(
            country_code=r["countryCode"],
            segment_id=r["segmentId"],
            year=r["year"],
            hectares=r["hectares"],
            qty_ks=r["qtyKs"],
            density=r["density"],
            price_exseed=r["priceExseed"],
            price_farmgate=r["priceFarmgate"],
            notes=r["notes"],
        ),
    )
    return {"written": count}


async def commit_plan(db: AsyncSession, rows: list[dict]) -> dict:
    count = await _replace_yearly(
        db,
        PlanYear,
        rows,
        lambda r: PlanYear(
            country_code=r["countryCode"],
            segment_id=r["segmentId"],
            year=r["year"],
            qty_ks=r["qtyKs"],
            value_usd=r["valueUsd"],
            net_price=r["netPrice"],
            fpi_qty_ks=r["fpiQtyKs"],
            comment=r["comment"],
        ),
    )
    return {"written": count}


async def commit_competitors(db: AsyncSession, rows: list[dict]) -> dict:
    keys = {(r["countryCode"], r["megaSegmentId"], r["year"]) for r in rows}
    for country, mega, year in keys:
        await db.execute(
            delete(CompetitorShare).where(
                CompetitorShare.country_code == country,
                CompetitorShare.mega_segment_id == mega,
                CompetitorShare.year == year,
            )
        )
    db.add_all(
        CompetitorShare(
            country_code=r["countryCode"],
            mega_segment_id=r["megaSegmentId"],
            competitor=r["competitor"],
            year=r["year"],
            share_pct=r["sharePct"],
            value_usd=r["valueUsd"],
            trend=r["trend"],
        )
        for r in rows
    )
    return {"written": len(rows)}


async def commit_grower(db: AsyncSession, rows: list[dict]) -> dict:
    for country, crop in {(r["countryCode"], r["cropLocal"]) for r in rows}:
        await db.execute(
            delete(GrowerPotential).where(
                GrowerPotential.country_code == country, GrowerPotential.crop_local == crop
            )
        )
    db.add_all(
        GrowerPotential(
            country_code=r["countryCode"],
            crop_local=r["cropLocal"],
            variety=r["variety"],
            owner=r["owner"],
            hectares=r["hectares"],
            density=r["density"],
            region=r["region"],
        )
        for r in rows
    )
    return {"written": len(rows)}


async def commit_actuals(db: AsyncSession, rows: list[dict]) -> dict:
    net_price = {
        (p.country_code, p.segment_id, p.year): p.net_price
        for p in (await db.execute(select(PlanYear))).scalars()
    }
    filled = 0
    for group in _chunks(rows):
        conditions = [
            and_(
                MonthlyActual.country_code == r["countryCode"],
                MonthlyActual.segment_id == r["segmentId"],
                MonthlyActual.year == r["year"],
                MonthlyActual.month == r["month"],
            )
            for r in group
        ]
        existing = {
            (a.country_code, a.segment_id, a.year, a.month): a
            for a in (await db.execute(select(MonthlyActual).where(or_(*conditions)))).scalars()
        }
        for r in group:
            value = r["valueUsd"]
            if value is None:
                value = r["qtyKs"] * net_price.get((r["countryCode"], r["segmentId"], r["year"]), 0.0)
                filled += 1
            key = (r["countryCode"], r["segmentId"], r["year"], r["month"])
            if key in existing:
                existing[key].qty_ks, existing[key].value_usd = r["qtyKs"], value
            else:
                db.add(
                    MonthlyActual(
                        country_code=key[0],
                        segment_id=key[1],
                        year=key[2],
                        month=key[3],
                        qty_ks=r["qtyKs"],
                        value_usd=value,
                    )
                )
    return {"written": len(rows), "valuesFilledFromPlanPrice": filled}


async def commit_assignments(db: AsyncSession, rows: list[dict]) -> dict:
    for r in rows:
        scopes = [
            ScopeIn(country_code=s["countryCode"], scope_type=s["scopeType"], scope_id=s["scopeId"])
            for s in r["scopes"]
        ]
        await upsert_user(db, r["email"], r["name"], r["role"], scopes)
    return {"users": len(rows), "scopes": sum(len(r["scopes"]) for r in rows)}


async def commit_seasonality(db: AsyncSession, rows: list[dict]) -> dict:
    for country, scope_type, scope_id in {(r["countryCode"], r["scopeType"], r["scopeId"]) for r in rows}:
        await db.execute(
            delete(Seasonality).where(
                Seasonality.country_code == country,
                Seasonality.scope_type == scope_type,
                Seasonality.scope_id == scope_id,
            )
        )
    db.add_all(
        Seasonality(
            country_code=r["countryCode"],
            scope_type=r["scopeType"],
            scope_id=r["scopeId"],
            month=r["month"],
            weight=r["weight"],
        )
        for r in rows
    )
    return {"keys": len({(r["countryCode"], r["scopeType"], r["scopeId"]) for r in rows})}


async def commit_budget_rates(db: AsyncSession, rows: list[dict]) -> dict:
    years = sorted({r["budgetYear"] for r in rows})
    await db.execute(delete(FxRate).where(FxRate.budget_year.in_(years)))
    db.add_all(
        FxRate(
            budget_year=r["budgetYear"],
            currency=r["currency"],
            currency_name=r["currencyName"],
            per_usd=r["perUsd"],
        )
        for r in rows
    )
    return {"budgetYears": years, "currencies": len(rows)}


async def commit_sac_sales(db: AsyncSession, rows: list[dict]) -> dict:
    actual_rows = [r for r in rows if r["measure"] == "actual"]
    forecast_rows = [r for r in rows if r["measure"] == "forecast"]
    summary = {"actualRows": len(actual_rows), "forecastRows": len(forecast_rows)}
    if actual_rows:
        summary["actuals"] = await commit_actuals(db, actual_rows)
    for country, snapshot in {(r["countryCode"], r["snapshot"]) for r in forecast_rows}:
        await db.execute(
            delete(IbpForecast).where(IbpForecast.country_code == country, IbpForecast.snapshot == snapshot)
        )
    db.add_all(
        IbpForecast(
            country_code=r["countryCode"],
            segment_id=r["segmentId"],
            variety=r["variety"],
            year=r["year"],
            month=r["month"],
            snapshot=r["snapshot"],
            qty_ks=r["qtyKs"],
            value_usd=r["valueUsd"],
            planner_id=r["plannerId"],
        )
        for r in forecast_rows
    )
    return summary


async def commit_variety_map(db: AsyncSession, rows: list[dict]) -> dict:
    for country in {r["countryCode"] for r in rows}:
        await db.execute(delete(VarietyMap).where(VarietyMap.country_code == country))
    db.add_all(
        VarietyMap(country_code=r["countryCode"], variety=r["variety"], segment_id=r["segmentId"]) for r in rows
    )
    return {"varieties": len(rows)}


COMMITTERS = {
    "hierarchy": commit_hierarchy,
    "market": commit_market,
    "plan": commit_plan,
    "competitors": commit_competitors,
    "grower": commit_grower,
    "actuals": commit_actuals,
    "assignments": commit_assignments,
    "seasonality": commit_seasonality,
    "budget_rates": commit_budget_rates,
    "variety_map": commit_variety_map,
    "sac_sales": commit_sac_sales,
}
