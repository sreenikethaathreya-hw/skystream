from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.demo import PROFILE_LABELS, SYNGENTA_VARIETIES
from app.models import (
    CompetitorShare,
    DemandEntry,
    DemoClock,
    GrowerPotential,
    MarketYear,
    MonthlyActual,
    MonthlyPlan,
    PlanYear,
    Segment,
)
from app.schemas.api import CompetitorOut, CubeOut, MonthEntryOut, SegmentCubeOut
from app.schemas.demand_math import SegmentContext, Thresholds
from app.services.cube_builder import Reference, build_mega, build_segment_context

LIVE_STATUSES = ("submitted", "approved", "discuss", "challenged")


def segment_label(segment: Segment) -> str:
    color = (segment.color or "").title()
    return f"{segment.id} · {PROFILE_LABELS.get(segment.profile, segment.profile)} {color}".strip()


async def get_clock(db: AsyncSession) -> DemoClock:
    clock = await db.get(DemoClock, 1)
    if clock is None:
        raise HTTPException(status_code=503, detail="Demo data is not seeded")
    return clock


async def load_reference(db: AsyncSession) -> Reference:
    async def all_of(model) -> list:
        return list((await db.execute(select(model))).scalars())

    return Reference(
        segments=await all_of(Segment),
        market=await all_of(MarketYear),
        plan=await all_of(PlanYear),
        monthly_plan=await all_of(MonthlyPlan),
        monthly_actuals=await all_of(MonthlyActual),
        competitors=await all_of(CompetitorShare),
        grower=await all_of(GrowerPotential),
    )


async def latest_entries(db: AsyncSession, year: int) -> dict[tuple[int, int], DemandEntry]:
    rows = (
        await db.execute(
            select(DemandEntry)
            .where(DemandEntry.year == year, DemandEntry.status.in_(LIVE_STATUSES))
            .order_by(DemandEntry.created_at)
        )
    ).scalars()
    return {(e.segment_id, e.month): e for e in rows}


async def build_context(db: AsyncSession, segment_id: int) -> tuple[SegmentContext, Segment]:
    clock = await get_clock(db)
    ref = await load_reference(db)
    segment = next((s for s in ref.segments if s.id == segment_id), None)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not in the locked scope")
    latest = await latest_entries(db, clock.year)
    submitted = {m: e.value for (s, m), e in latest.items() if s == segment_id and e.source == "live"}
    mega = build_mega(ref, clock.year)
    return build_segment_context(ref, segment_id, clock.year, clock.month, submitted, mega), segment


async def build_cube(db: AsyncSession) -> CubeOut:
    clock = await get_clock(db)
    ref = await load_reference(db)
    mega = build_mega(ref, clock.year)
    latest = await latest_entries(db, clock.year)
    market_by_key = {(m.segment_id, m.year): m for m in ref.market}
    plan_by_key = {(p.segment_id, p.year): p for p in ref.plan}

    segments = []
    for seg in sorted(ref.segments, key=lambda s: s.id):
        seg_entries = [e for (s, _), e in latest.items() if s == seg.id]
        submitted = {e.month: e.value for e in seg_entries if e.source == "live"}
        plan = plan_by_key.get((seg.id, clock.year))
        segments.append(
            SegmentCubeOut(
                id=seg.id,
                label=segment_label(seg),
                description=seg.description,
                color=seg.color,
                profile=seg.profile,
                owner_id=seg.owner_id,
                plan_comment=plan.comment if plan else None,
                market_notes=market_by_key[(seg.id, clock.year)].notes or {},
                context=build_segment_context(ref, seg.id, clock.year, clock.month, submitted, mega),
                latest_entries=[
                    MonthEntryOut(
                        id=e.id,
                        month=e.month,
                        value=e.value,
                        low=e.low,
                        high=e.high,
                        status=e.status,
                        user_id=e.user_id,
                    )
                    for e in sorted(seg_entries, key=lambda e: e.month)
                ],
            )
        )

    competitors = [c for c in ref.competitors if c.year == clock.year]
    return CubeOut(
        year=clock.year,
        clock_month=clock.month,
        thresholds=Thresholds(),
        competitors=[
            CompetitorOut(name=c.competitor, share_pct=c.share_pct, trend=c.trend)
            for c in sorted(competitors, key=lambda c: -c.share_pct)
        ],
        varieties=SYNGENTA_VARIETIES,
        segments=segments,
    )
