"""Turn an imported IBP forecast snapshot into the reps' demand entries.

Reps commit demand by variety in IBP (SME answer). Skystream rolls it up per micro-segment and month, runs the
same flags and lead rules as Capture on the server, and asks the rep to justify only the flagged numbers.
The number is the rep's own, so this is not a forecasting model.
"""

from collections import defaultdict

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppUser, DemandEntry, IbpForecast, Segment
from app.schemas.demand_math import EntryInput
from app.services.context_service import segment_contexts
from app.services.demand_math import compute_impact
from app.services.flags import evaluate_flags
from app.services.lead_rules import evaluate_rules
from app.services.rule_service import active_specs
from app.services.settings_service import get_app_settings
from app.services.user_service import UNASSIGNED, rep_ids_covering

REPLACEABLE = ("submitted", "discuss", "challenged", "approved", "needs_justification")
UNCHANGED_KS = 0.5


async def _owner(planners: set[str], covering: list[str], registered_reps: set[str]) -> str:
    named = sorted(p for p in planners if p in registered_reps)
    if len(named) == 1:
        return named[0]
    if len(covering) == 1:
        return covering[0]
    return UNASSIGNED


async def apply_latest_stored(db: AsyncSession) -> dict:
    """When an admin switches the demand source to IBP, turn the latest stored snapshot into entries."""
    forecasts = (await db.execute(select(IbpForecast))).scalars().all()
    newest: dict[tuple[str, int, int, int], str] = {}
    for f in forecasts:
        key = (f.country_code, f.segment_id, f.year, f.month)
        newest[key] = max(newest.get(key, ""), f.snapshot)
    rows = [
        {
            "countryCode": f.country_code,
            "segmentId": f.segment_id,
            "year": f.year,
            "month": f.month,
            "snapshot": f.snapshot,
            "qtyKs": f.qty_ks,
            "valueUsd": f.value_usd,
            "plannerId": f.planner_id,
        }
        for f in forecasts
        if newest[(f.country_code, f.segment_id, f.year, f.month)] == f.snapshot
    ]
    return await apply_forecast_snapshot(db, rows) if rows else {"created": 0}


async def apply_forecast_snapshot(db: AsyncSession, rows: list[dict]) -> dict:
    """Create or update `source="ibp"` entries for the forecast rows of one committed SAC upload."""
    settings = await get_app_settings(db)
    if settings.demand_source != "ibp":
        return {"created": 0, "note": "Demand source is 'typed in Capture'; the forecast is shown for reference only"}

    # Latest snapshot per country/segment/month, summed over varieties.
    latest: dict[tuple[str, int, int, int], dict] = {}
    for r in rows:
        key = (r["countryCode"], r["segmentId"], r["year"], r["month"])
        cur = latest.get(key)
        if cur is None or r["snapshot"] > cur["snapshot"]:
            latest[key] = {"snapshot": r["snapshot"], "qtyKs": 0.0, "valueUsd": None, "planners": set()}
        if latest[key]["snapshot"] == r["snapshot"]:
            latest[key]["qtyKs"] += r["qtyKs"]
            if r["valueUsd"] is not None:
                latest[key]["valueUsd"] = (latest[key]["valueUsd"] or 0.0) + r["valueUsd"]
            if r.get("plannerId"):
                latest[key]["planners"].add(r["plannerId"])

    segments = {s.id: s for s in (await db.execute(select(Segment))).scalars()}
    registered = {
        u.id
        for u in (await db.execute(select(AppUser).where(AppUser.role == "rep", AppUser.active.is_(True)))).scalars()
    }
    by_scope: dict[tuple[str, str], list[int]] = defaultdict(list)
    for country, segment_id, _, _ in latest:
        by_scope[(country, segments[segment_id].mega_segment_id)].append(segment_id)

    stats = defaultdict(int)
    for (country, mega), segment_ids in by_scope.items():
        period, contexts = await segment_contexts(db, country, mega, sorted(set(segment_ids)))
        rules = await active_specs(db, country, mega)
        covering = await rep_ids_covering(db, country, [segments[s] for s in segment_ids])
        existing = {
            (e.segment_id, e.month): e
            for e in (
                await db.execute(
                    select(DemandEntry)
                    .where(
                        DemandEntry.country_code == country,
                        DemandEntry.year == period.year,
                        DemandEntry.segment_id.in_(segment_ids),
                        DemandEntry.source.in_(("live", "ibp")),
                        DemandEntry.status.in_(REPLACEABLE),
                    )
                    .order_by(DemandEntry.created_at)
                )
            ).scalars()
        }
        for segment_id in sorted(set(segment_ids)):
            if segment_id not in contexts:
                stats["skippedNoMarket"] += sum(1 for k in latest if k[:2] == (country, segment_id))
                continue
            _, ctx = contexts[segment_id]
            months = {
                k[3]: v for k, v in latest.items() if k[0] == country and k[1] == segment_id and k[2] == period.year
            }
            for month, fc in sorted(months.items()):
                if month < ctx.clock_month:
                    stats["skippedClosed"] += 1
                    continue
                # The snapshot's other open months count as submitted; this month's baseline stays the
                # previously committed number (or the plan), so a share jump is measured against it.
                others = {str(m): v["qtyKs"] for m, v in months.items() if m >= ctx.clock_month and m != month}
                month_ctx = ctx.model_copy(update={"submitted": {**ctx.submitted, **others}})
                prior = existing.get((segment_id, month))
                if prior is not None and prior.source == "ibp" and abs(prior.value - fc["qtyKs"]) < UNCHANGED_KS:
                    stats["unchanged"] += 1
                    continue
                qty = fc["qtyKs"]
                price = fc["valueUsd"] / qty if fc["valueUsd"] and qty else None
                entry = EntryInput(month=month, value=qty, low=qty, high=qty, price=price)
                impact = compute_impact(month_ctx, entry, settings.thresholds)
                flags = [
                    *evaluate_flags(month_ctx, entry, impact, settings.thresholds),
                    *evaluate_rules(month_ctx, segment_id, entry, impact, rules),
                ]
                await db.execute(
                    update(DemandEntry)
                    .where(
                        DemandEntry.country_code == country,
                        DemandEntry.segment_id == segment_id,
                        DemandEntry.year == period.year,
                        DemandEntry.month == month,
                        DemandEntry.source.in_(("live", "ibp")),
                        DemandEntry.status.in_(REPLACEABLE),
                    )
                    .values(status="superseded")
                )
                owner = await _owner(fc["planners"], covering.get(segment_id, []), registered)
                db.add(
                    DemandEntry(
                        user_id=owner,
                        country_code=country,
                        segment_id=segment_id,
                        year=period.year,
                        month=month,
                        value=qty,
                        low=qty,
                        high=qty,
                        price=price,
                        impact=impact.model_dump(by_alias=True),
                        flags=[f.model_dump(by_alias=True) for f in flags],
                        status="needs_justification" if flags else "submitted",
                        source="ibp",
                        snapshot=fc["snapshot"],
                    )
                )
                stats["created"] += 1
                stats["needsJustification"] += bool(flags)
                stats["unassigned"] += owner == UNASSIGNED
    await db.flush()
    return dict(stats)
