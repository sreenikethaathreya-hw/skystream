"""Scope-aware reference loading, calendar, and the cube the browser runs its math on."""

from collections import Counter
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants.demo import MAX_VARIETY_OPTIONS, PROFILE_LABELS, SYNGENTA_VARIETIES
from app.models import (
    CompetitorShare,
    Country,
    DemandEntry,
    DemoClock,
    GrowerPotential,
    MarketYear,
    MonthlyActual,
    MonthlyPlan,
    PlanYear,
    Segment,
)
from app.schemas.api import CompetitorOut, CubeOut, MonthEntryOut, ScopeOptionOut, SegmentCubeOut
from app.schemas.demand_math import SegmentContext
from app.services.cube_builder import Reference, build_mega, build_segment_context, last_year_basis
from app.services.settings_service import get_app_settings
from app.services.user_service import CurrentUser, can_submit, owners_by_segment

LIVE_STATUSES = ("submitted", "approved", "discuss", "challenged")


def segment_label(segment: Segment) -> str:
    color = (segment.color or "").title()
    return f"{segment.id} · {PROFILE_LABELS.get(segment.profile, segment.profile.title())} {color}".strip()


@dataclass
class Period:
    year: int
    clock_month: int

    @property
    def closed(self) -> bool:
        return self.clock_month > 12


async def current_period(db: AsyncSession, country_code: str) -> Period:
    """Open months start at the demo clock, or (real mode) the month after the last uploaded actuals."""
    if get_settings().is_demo:
        clock = await db.get(DemoClock, 1)
        if clock is None:
            raise HTTPException(status_code=503, detail="Demo data is not seeded")
        return Period(clock.year, clock.month)
    year = (await get_app_settings(db)).current_year
    last = (
        await db.execute(
            select(func.max(MonthlyActual.month)).where(
                MonthlyActual.country_code == country_code, MonthlyActual.year == year
            )
        )
    ).scalar_one_or_none()
    return Period(year, (last or 0) + 1)


async def _active_segments(db: AsyncSession, country_code: str, mega: str, year: int) -> list[Segment]:
    rows = await db.execute(
        select(Segment)
        .join(MarketYear, MarketYear.segment_id == Segment.id)
        .where(
            Segment.mega_segment_id == mega,
            MarketYear.country_code == country_code,
            MarketYear.year == year,
            MarketYear.hectares > 0,
        )
        .order_by(Segment.id)
    )
    return list(rows.scalars())


async def load_reference(db: AsyncSession, country_code: str, segments: list[Segment]) -> Reference:
    ids = [s.id for s in segments]
    mega_ids = {s.mega_segment_id for s in segments}
    crops = {s.mega_segment_desc.upper() for s in segments}

    async def rows(model, *conditions) -> list:
        return list((await db.execute(select(model).where(*conditions))).scalars())

    def per_segment(model) -> tuple:
        return model.country_code == country_code, model.segment_id.in_(ids)

    return Reference(
        segments=segments,
        market=await rows(MarketYear, *per_segment(MarketYear)),
        plan=await rows(PlanYear, *per_segment(PlanYear)),
        monthly_plan=await rows(MonthlyPlan, *per_segment(MonthlyPlan)),
        monthly_actuals=await rows(MonthlyActual, *per_segment(MonthlyActual)),
        competitors=await rows(
            CompetitorShare,
            CompetitorShare.country_code == country_code,
            CompetitorShare.mega_segment_id.in_(mega_ids),
        ),
        grower=await rows(
            GrowerPotential,
            GrowerPotential.country_code == country_code,
            GrowerPotential.crop_local.in_(crops),
        ),
    )


async def latest_entries(
    db: AsyncSession, country_code: str, year: int, segment_ids: list[int]
) -> dict[tuple[int, int], DemandEntry]:
    rows = (
        await db.execute(
            select(DemandEntry)
            .where(
                DemandEntry.country_code == country_code,
                DemandEntry.year == year,
                DemandEntry.segment_id.in_(segment_ids),
                DemandEntry.status.in_(LIVE_STATUSES),
            )
            .order_by(DemandEntry.created_at)
        )
    ).scalars()
    return {(e.segment_id, e.month): e for e in rows}


async def scope_options(db: AsyncSession, user: CurrentUser) -> list[ScopeOptionOut]:
    year = (await get_app_settings(db)).current_year
    if get_settings().is_demo:
        year = (await current_period(db, "ES")).year
    rows = (
        await db.execute(
            select(
                MarketYear.country_code,
                Segment.mega_segment_id,
                Segment.mega_segment_desc,
                Segment.species,
                Segment.id,
            )
            .join(Segment, Segment.id == MarketYear.segment_id)
            .where(MarketYear.year == year, MarketYear.hectares > 0)
        )
    ).all()
    names = {c.code: c.name for c in (await db.execute(select(Country))).scalars()}
    grouped: dict[tuple[str, str], dict] = {}
    for country, mega, mega_desc, species, segment_id in rows:
        key = (country, mega)
        item = grouped.setdefault(key, {"desc": mega_desc, "species": species, "segments": set()})
        item["segments"].add(segment_id)
    options = []
    for (country, mega), item in sorted(grouped.items()):
        visible = (
            user.role in ("lead", "admin")
            or get_settings().is_demo
            or any(
                s.country_code == country
                and (
                    (s.scope_type == "mega" and s.scope_id == mega)
                    or (
                        s.scope_type == "micro"
                        and s.scope_id.isdigit()
                        and int(s.scope_id) in item["segments"]
                    )
                )
                for s in user.scopes
            )
        )
        if visible:
            options.append(
                ScopeOptionOut(
                    country_code=country,
                    country_name=names.get(country, country),
                    species=item["species"],
                    mega_segment_id=mega,
                    mega_segment_desc=item["desc"],
                    segments=len(item["segments"]),
                )
            )
    return options


async def resolve_scope(
    db: AsyncSession, user: CurrentUser, country: str | None, mega: str | None
) -> tuple[str, str]:
    options = await scope_options(db, user)
    if not options:
        raise HTTPException(status_code=404, detail="No data is loaded for your segments yet")
    if country is None or mega is None:
        return options[0].country_code, options[0].mega_segment_id
    if not any(o.country_code == country.upper() and o.mega_segment_id == mega for o in options):
        raise HTTPException(status_code=403, detail="That country and segment are not in your scope")
    return country.upper(), mega


def variety_options(ref: Reference) -> list[str]:
    counts = Counter(g.variety for g in ref.grower if g.owner == "syngenta" and g.variety)
    top = [v.title() for v, _ in counts.most_common(MAX_VARIETY_OPTIONS)]
    return top or SYNGENTA_VARIETIES


async def build_context(
    db: AsyncSession, country_code: str, segment_id: int
) -> tuple[SegmentContext, Segment, Reference]:
    segment = await db.get(Segment, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Unknown micro-segment")
    period = await current_period(db, country_code)
    segments = await _active_segments(db, country_code, segment.mega_segment_id, period.year)
    if segment_id not in {s.id for s in segments}:
        raise HTTPException(
            status_code=404, detail=f"No {period.year} market for this segment in {country_code}"
        )
    ref = await load_reference(db, country_code, segments)
    latest = await latest_entries(db, country_code, period.year, [segment_id])
    submitted = {m: e.value for (_, m), e in latest.items() if e.source == "live"}
    mega = build_mega(ref, period.year)
    ctx = build_segment_context(ref, segment_id, period.year, period.clock_month, submitted, mega)
    return ctx, segment, ref


async def build_cube(
    db: AsyncSession, user: CurrentUser, country: str | None, mega_id: str | None
) -> CubeOut:
    from app.services.rule_service import active_specs  # rule_service imports segment_label from here

    country_code, mega_id = await resolve_scope(db, user, country, mega_id)
    period = await current_period(db, country_code)
    app_settings = await get_app_settings(db)
    segments = await _active_segments(db, country_code, mega_id, period.year)
    ref = await load_reference(db, country_code, segments)
    mega = build_mega(ref, period.year)
    latest = await latest_entries(db, country_code, period.year, [s.id for s in segments])
    owners = await owners_by_segment(db, country_code, segments)
    market_by_key = {(m.segment_id, m.year): m for m in ref.market}
    plan_by_key = {(p.segment_id, p.year): p for p in ref.plan}
    plan_basis = {m.segment_id: m.basis for m in ref.monthly_plan if m.year == period.year}

    out_segments = []
    for seg in segments:
        seg_entries = [e for (s, _), e in latest.items() if s == seg.id]
        submitted = {e.month: e.value for e in seg_entries if e.source == "live"}
        plan = plan_by_key.get((seg.id, period.year))
        out_segments.append(
            SegmentCubeOut(
                id=seg.id,
                label=segment_label(seg),
                description=seg.description,
                color=seg.color,
                profile=seg.profile,
                editable=can_submit(user, country_code, seg) and not period.closed,
                owner_names=owners.get(seg.id, []),
                plan_basis=plan_basis.get(seg.id, "none"),
                last_year_basis=last_year_basis(ref, seg.id, period.year),
                plan_comment=plan.comment if plan else None,
                market_notes=market_by_key[(seg.id, period.year)].notes or {},
                context=build_segment_context(ref, seg.id, period.year, period.clock_month, submitted, mega),
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

    country_row = await db.get(Country, country_code)
    competitors = [c for c in ref.competitors if c.year == period.year]
    first = segments[0] if segments else None
    return CubeOut(
        country_code=country_code,
        country_name=country_row.name if country_row else country_code,
        mega_segment_id=mega_id,
        mega_segment_desc=first.mega_segment_desc if first else mega_id,
        species=first.species if first else None,
        currency=country_row.currency if country_row else app_settings.currency,
        year=period.year,
        clock_month=period.clock_month,
        year_closed=period.closed,
        thresholds=app_settings.thresholds,
        rules=await active_specs(db, country_code, mega_id),
        competitors=[
            CompetitorOut(name=c.competitor, share_pct=c.share_pct, trend=c.trend)
            for c in sorted(competitors, key=lambda c: -c.share_pct)
        ],
        varieties=variety_options(ref),
        segments=out_segments,
    )
