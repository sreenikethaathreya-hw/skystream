from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.decision_provider import JustificationInput, decision_policy, get_decision_provider
from app.ai.questions import DRIVER_LABELS
from app.constants.demo import MONTH_NAMES
from app.database import async_session
from app.ingest.sac import NO_VARIETY
from app.models import Claim, DemandEntry, IbpForecast, Segment
from app.schemas.api import AnalyzeOut, ClaimOut, EntryIn, EntryOut, JustifyIn
from app.schemas.claims import StructuredClaim, TriageDecision
from app.schemas.demand_math import EntryInput, Flag, Impact, SegmentContext
from app.services.claim_checks import claim_mismatches
from app.services.context_service import COMMITTED_SOURCES, build_context, segment_label, variety_options
from app.services.cube_builder import Reference
from app.services.demand_math import compute_impact
from app.services.flags import evaluate_flags
from app.services.lead_rules import evaluate_rules, unmet_driver_flags
from app.services.rule_service import active_specs
from app.services.seed_service import signal_for
from app.services.settings_service import AppSettings, get_app_settings
from app.services.user_service import UNASSIGNED, CurrentUser, can_submit, user_names

REPLACEABLE = ("submitted", "discuss", "challenged", "approved", "needs_justification")
JUSTIFIABLE = ("needs_justification", "submitted", "discuss", "challenged")


def _entry_summary(month: int, entry: EntryInput, impact: Impact) -> str:
    return (
        f"{MONTH_NAMES[month - 1]} demand {entry.value:,.0f} KS (plan {impact.month_expected:,.0f}, "
        f"range {entry.low:,.0f}-{entry.high:,.0f}); full year {impact.fy_estimate:,.0f} KS vs plan "
        f"{impact.plan_fy:,.0f}; volume share {impact.volume_share:.1%} (plan {impact.plan_volume_share:.1%})"
    )


def _notes_text(notes: dict, plan_comment: str | None) -> str:
    parts = [f"{k}: {v}" for k, v in notes.items() if v]
    if plan_comment:
        parts.append(f"rep comment: {plan_comment}")
    return " | ".join(parts) or "none"


async def _evaluate(db: AsyncSession, body: EntryIn, settings: AppSettings):
    ctx, segment, ref = await build_context(db, body.country_code, body.segment_id)
    if body.month < ctx.clock_month:
        raise HTTPException(status_code=400, detail="That month is closed; actuals are already in")
    entry = EntryInput(month=body.month, value=body.value, low=body.low, high=body.high, price=body.price)
    impact = compute_impact(ctx, entry, settings.thresholds)
    rules = await active_specs(db, body.country_code, segment.mega_segment_id)
    flags = [
        *evaluate_flags(ctx, entry, impact, settings.thresholds),
        *evaluate_rules(ctx, segment.id, entry, impact, rules),
    ]
    return ctx, segment, ref, entry, impact, flags, rules


async def _structure(
    ctx: SegmentContext,
    segment: Segment,
    ref: Reference,
    body: EntryIn,
    entry: EntryInput,
    impact: Impact,
    flags: list[Flag],
    settings: AppSettings,
    varieties: list[str] | None = None,
) -> StructuredClaim | None:
    if not body.justification or not body.justification.strip():
        return None
    market = next(m for m in ref.market if m.segment_id == segment.id and m.year == ctx.year)
    plan = next((p for p in ref.plan if p.segment_id == segment.id and p.year == ctx.year), None)
    competitors = sorted(
        {c.competitor for c in ref.competitors if c.year == ctx.year} - {"Syngenta", "Others"}
    )
    claim = await get_decision_provider().structure_justification(
        JustificationInput(
            sentence=body.justification.strip(),
            segment_label=f"{segment_label(segment)} ({segment.description})",
            entry_summary=_entry_summary(body.month, entry, impact),
            flags=flags,
            market_notes=_notes_text(market.notes or {}, plan.comment if plan else None),
            competitors=competitors,
            varieties=varieties or variety_options(ref),
            flag_direction="up" if entry.value > impact.month_expected else "down",
        ),
        decision_policy(settings),
    )
    mismatches = claim_mismatches(claim.direction, claim.magnitude, entry.value, impact.month_expected)
    return claim.model_copy(update={"mismatches": mismatches})


async def analyze(db: AsyncSession, body: EntryIn) -> AnalyzeOut:
    settings = await get_app_settings(db)
    ctx, segment, ref, entry, impact, flags, rules = await _evaluate(db, body, settings)
    claim = await _structure(ctx, segment, ref, body, entry, impact, flags, settings)
    if claim:
        unmet = unmet_driver_flags(rules, flags, claim.driver, DRIVER_LABELS)
        claim = claim.model_copy(update={"mismatches": [*claim.mismatches, *unmet]})
    return AnalyzeOut(impact=impact, flags=flags, claim=claim)


async def create_entry(db: AsyncSession, user: CurrentUser, body: EntryIn) -> EntryOut:
    settings = await get_app_settings(db)
    if settings.demand_source == "ibp":
        raise HTTPException(
            status_code=409,
            detail="Demand comes from IBP: change the number in IBP, then justify it here if it is flagged",
        )
    ctx, segment, ref, entry, impact, flags, rules = await _evaluate(db, body, settings)
    if not can_submit(user, body.country_code, segment):
        raise HTTPException(status_code=403, detail="Only a rep assigned to this segment can submit for it")
    if flags and not (body.justification or "").strip():
        raise HTTPException(status_code=422, detail="A justification is required when flags fire")
    claim = await _structure(ctx, segment, ref, body, entry, impact, flags, settings)
    if claim:
        flags = [*flags, *claim.mismatches, *unmet_driver_flags(rules, flags, claim.driver, DRIVER_LABELS)]

    await db.execute(
        update(DemandEntry)
        .where(
            DemandEntry.country_code == body.country_code,
            DemandEntry.segment_id == body.segment_id,
            DemandEntry.year == ctx.year,
            DemandEntry.month == body.month,
            DemandEntry.source.in_(COMMITTED_SOURCES),
            DemandEntry.status.in_(REPLACEABLE),
        )
        .values(status="superseded")
    )
    row = DemandEntry(
        user_id=user.id,
        country_code=body.country_code,
        segment_id=body.segment_id,
        year=ctx.year,
        month=body.month,
        value=body.value,
        low=body.low,
        high=body.high,
        price=body.price,
        justification=(body.justification or "").strip() or None,
        impact=impact.model_dump(by_alias=True),
        flags=[f.model_dump(by_alias=True) for f in flags],
        status="submitted",
        source="live",
    )
    db.add(row)
    await db.flush()
    claim_row = None
    if claim:
        claim_row = Claim(
            entry_id=row.id,
            driver=claim.driver,
            direction=claim.direction,
            magnitude=claim.magnitude,
            competitor=claim.competitor,
            variety=claim.variety,
            evidence_source=claim.evidence_source,
            verifiable=claim.verifiable,
            consistent_with_notes=claim.consistent_with_notes,
            specificity=claim.specificity,
            addresses_flags=claim.addresses_flags,
            summary=claim.summary,
            decisions={k: v.model_dump(by_alias=True) for k, v in claim.decisions.items()},
            provider=claim.provider,
            signal=signal_for(claim.driver),
            check_year=ctx.year,
            check_month=body.month,
        )
        db.add(claim_row)
    await db.commit()
    return to_out(row, claim_row, {segment.id: segment}, {user.id: user.name})


def _claim_row(entry_id: str, claim: StructuredClaim, year: int, month: int) -> Claim:
    return Claim(
        entry_id=entry_id,
        driver=claim.driver,
        direction=claim.direction,
        magnitude=claim.magnitude,
        competitor=claim.competitor,
        variety=claim.variety,
        evidence_source=claim.evidence_source,
        verifiable=claim.verifiable,
        consistent_with_notes=claim.consistent_with_notes,
        specificity=claim.specificity,
        addresses_flags=claim.addresses_flags,
        summary=claim.summary,
        decisions={k: v.model_dump(by_alias=True) for k, v in claim.decisions.items()},
        provider=claim.provider,
        signal=signal_for(claim.driver),
        check_year=year,
        check_month=month,
    )


async def ibp_varieties(db: AsyncSession, row: DemandEntry) -> list[str]:
    rows = await db.execute(
        select(IbpForecast.variety).where(
            IbpForecast.country_code == row.country_code,
            IbpForecast.segment_id == row.segment_id,
            IbpForecast.year == row.year,
            IbpForecast.month == row.month,
            IbpForecast.snapshot == row.snapshot,
        )
    )
    return sorted({v for (v,) in rows.all()} - {NO_VARIETY})


async def justify_entry(db: AsyncSession, user: CurrentUser, entry_id: str, body: JustifyIn) -> EntryOut:
    """The rep's justification (and optional range) for a number committed in IBP. The number stays IBP's."""
    row = await db.get(DemandEntry, entry_id)
    if row is None or row.source != "ibp":
        raise HTTPException(status_code=404, detail="IBP entry not found")
    if row.status not in JUSTIFIABLE:
        raise HTTPException(status_code=409, detail=f"This entry is {row.status}")
    segment = await db.get(Segment, row.segment_id)
    if row.user_id != user.id and not can_submit(user, row.country_code, segment):
        raise HTTPException(status_code=403, detail="Only the rep who owns this number can justify it")
    low = body.low if body.low is not None else row.low
    high = body.high if body.high is not None else row.high
    if not low <= row.value <= high:
        raise HTTPException(status_code=422, detail="The range must include the IBP number")
    request = EntryIn(
        country_code=row.country_code,
        segment_id=row.segment_id,
        month=row.month,
        value=row.value,
        low=low,
        high=high,
        price=row.price,
        justification=body.justification,
    )
    settings = await get_app_settings(db)
    ctx, segment, ref, entry, impact, flags, rules = await _evaluate(db, request, settings)
    if flags and not (body.justification or "").strip():
        raise HTTPException(status_code=422, detail="A justification is required when flags fire")
    varieties = await ibp_varieties(db, row)
    claim = await _structure(ctx, segment, ref, request, entry, impact, flags, settings, varieties or None)
    if claim:
        flags = [*flags, *claim.mismatches, *unmet_driver_flags(rules, flags, claim.driver, DRIVER_LABELS)]

    row.low, row.high = low, high
    row.justification = (body.justification or "").strip() or None
    row.impact = impact.model_dump(by_alias=True)
    row.flags = [f.model_dump(by_alias=True) for f in flags]
    if row.user_id == UNASSIGNED:
        row.user_id = user.id
    if row.status == "needs_justification":
        row.status = "submitted"
    await db.execute(delete(Claim).where(Claim.entry_id == row.id))
    claim_row = _claim_row(row.id, claim, ctx.year, row.month) if claim else None
    if claim_row:
        db.add(claim_row)
    await db.commit()
    return to_out(row, claim_row, {segment.id: segment}, {user.id: user.name})


async def polish_claim_summary(entry_id: str) -> None:
    async with async_session() as db:
        claim = (await db.execute(select(Claim).where(Claim.entry_id == entry_id))).scalar_one_or_none()
        entry = await db.get(DemandEntry, entry_id)
        if claim is None or entry is None or not entry.justification:
            return
        polished = await get_decision_provider().polish_summary(entry.justification, claim.summary or "")
        if polished:
            claim.summary = polished
            await db.commit()


def claim_out(claim: Claim) -> ClaimOut:
    return ClaimOut(
        driver=claim.driver,
        direction=claim.direction,
        magnitude=claim.magnitude,
        competitor=claim.competitor,
        variety=claim.variety,
        evidence_source=claim.evidence_source,
        verifiable=claim.verifiable,
        consistent_with_notes=claim.consistent_with_notes,
        specificity=claim.specificity,
        addresses_flags=claim.addresses_flags,
        summary=claim.summary,
        provider=claim.provider,
        signal=claim.signal,
        check_year=claim.check_year,
        check_month=claim.check_month,
        resolution=claim.resolution,
        resolution_detail=claim.resolution_detail,
        decisions=claim.decisions or {},
    )


def to_out(
    entry: DemandEntry, claim: Claim | None, segments: dict[int, Segment], names: dict[str, str]
) -> EntryOut:
    segment = segments.get(entry.segment_id)
    return EntryOut(
        id=entry.id,
        user_id=entry.user_id,
        country_code=entry.country_code,
        segment_id=entry.segment_id,
        segment_label=segment_label(segment) if segment else str(entry.segment_id),
        year=entry.year,
        month=entry.month,
        value=entry.value,
        low=entry.low,
        high=entry.high,
        price=entry.price,
        justification=entry.justification,
        impact=entry.impact,
        flags=[Flag.model_validate(f) for f in entry.flags or []],
        status=entry.status,
        source=entry.source,
        snapshot=entry.snapshot,
        user_name=names.get(entry.user_id, "No rep assigned" if entry.user_id == UNASSIGNED else entry.user_id),
        triage=TriageDecision.model_validate(entry.triage) if entry.triage else None,
        reviewed_by=entry.reviewed_by,
        created_at=entry.created_at,
        claim=claim_out(claim) if claim else None,
    )


def scope_filter(query, country_code: str | None, mega: str | None):
    if country_code:
        query = query.where(DemandEntry.country_code == country_code.upper())
    if mega:
        query = query.join(Segment, Segment.id == DemandEntry.segment_id).where(
            Segment.mega_segment_id == mega
        )
    return query


async def list_entries(
    db: AsyncSession,
    country_code: str | None = None,
    mega: str | None = None,
    segment_id: int | None = None,
    user_id: str | None = None,
    include_superseded: bool = False,
    limit: int = 200,
) -> list[EntryOut]:
    query = (
        select(DemandEntry, Claim)
        .outerjoin(Claim, Claim.entry_id == DemandEntry.id)
        .order_by(DemandEntry.created_at.desc(), DemandEntry.month.desc())
        .limit(limit)
    )
    query = scope_filter(query, country_code, mega)
    if segment_id is not None:
        query = query.where(DemandEntry.segment_id == segment_id)
    if user_id is not None:
        query = query.where(DemandEntry.user_id == user_id)
    if not include_superseded:
        query = query.where(DemandEntry.status != "superseded")
    rows = (await db.execute(query)).all()
    segments = {s.id: s for s in (await db.execute(select(Segment))).scalars()}
    names = await user_names(db)
    return [to_out(entry, claim, segments, names) for entry, claim in rows]
