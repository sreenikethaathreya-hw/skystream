from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.decision_provider import JustificationInput, get_decision_provider
from app.constants.demo import DEMO_USERS, MONTH_NAMES, SYNGENTA_VARIETIES, DemoUser
from app.database import async_session
from app.models import Claim, CompetitorShare, DemandEntry, Segment
from app.schemas.api import AnalyzeOut, ClaimOut, EntryIn, EntryOut
from app.schemas.claims import StructuredClaim, TriageDecision
from app.schemas.demand_math import EntryInput, Flag, Impact, SegmentContext
from app.services.claim_checks import claim_mismatches
from app.services.context_service import build_context, get_clock, load_reference, segment_label
from app.services.demand_math import compute_impact
from app.services.flags import evaluate_flags
from app.services.seed_service import signal_for

REPLACEABLE = ("submitted", "discuss", "challenged", "approved")


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


async def _competitor_names(db: AsyncSession, year: int) -> list[str]:
    rows = (
        await db.execute(select(CompetitorShare.competitor).where(CompetitorShare.year == year))
    ).scalars()
    return sorted({c for c in rows if c not in ("Syngenta", "Others")})


async def _evaluate(db: AsyncSession, body: EntryIn):
    ctx, segment = await build_context(db, body.segment_id)
    if body.month < ctx.clock_month:
        raise HTTPException(status_code=400, detail="That month is closed; actuals are already in")
    entry = EntryInput(month=body.month, value=body.value, low=body.low, high=body.high, price=body.price)
    impact = compute_impact(ctx, entry)
    flags = evaluate_flags(ctx, entry, impact)
    return ctx, segment, entry, impact, flags


async def _structure(
    db: AsyncSession,
    ctx: SegmentContext,
    segment: Segment,
    body: EntryIn,
    entry: EntryInput,
    impact: Impact,
    flags: list[Flag],
) -> StructuredClaim | None:
    if not body.justification or not body.justification.strip():
        return None
    ref = await load_reference(db)
    market = next(m for m in ref.market if m.segment_id == segment.id and m.year == ctx.year)
    plan = next((p for p in ref.plan if p.segment_id == segment.id and p.year == ctx.year), None)
    claim = await get_decision_provider().structure_justification(
        JustificationInput(
            sentence=body.justification.strip(),
            segment_label=f"{segment_label(segment)} ({segment.description})",
            entry_summary=_entry_summary(body.month, entry, impact),
            flags=flags,
            market_notes=_notes_text(market.notes or {}, plan.comment if plan else None),
            competitors=await _competitor_names(db, ctx.year),
            varieties=SYNGENTA_VARIETIES,
            flag_direction="up" if entry.value > impact.month_expected else "down",
        )
    )
    mismatches = claim_mismatches(claim.direction, claim.magnitude, entry.value, impact.month_expected)
    return claim.model_copy(update={"mismatches": mismatches})


async def analyze(db: AsyncSession, body: EntryIn) -> AnalyzeOut:
    ctx, segment, entry, impact, flags = await _evaluate(db, body)
    claim = await _structure(db, ctx, segment, body, entry, impact, flags)
    return AnalyzeOut(impact=impact, flags=flags, claim=claim)


async def create_entry(db: AsyncSession, user: DemoUser, body: EntryIn) -> EntryOut:
    ctx, segment, entry, impact, flags = await _evaluate(db, body)
    if user.role != "rep" or segment.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owning rep can submit for this segment")
    if flags and not (body.justification or "").strip():
        raise HTTPException(status_code=422, detail="A justification is required when flags fire")
    claim = await _structure(db, ctx, segment, body, entry, impact, flags)
    if claim:
        flags = [*flags, *claim.mismatches]

    await db.execute(
        update(DemandEntry)
        .where(
            DemandEntry.segment_id == body.segment_id,
            DemandEntry.year == ctx.year,
            DemandEntry.month == body.month,
            DemandEntry.source == "live",
            DemandEntry.status.in_(REPLACEABLE),
        )
        .values(status="superseded")
    )
    row = DemandEntry(
        user_id=user.id,
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
    return to_out(row, claim_row, {segment.id: segment})


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


def to_out(entry: DemandEntry, claim: Claim | None, segments: dict[int, Segment]) -> EntryOut:
    user = DEMO_USERS.get(entry.user_id)
    segment = segments.get(entry.segment_id)
    return EntryOut(
        id=entry.id,
        user_id=entry.user_id,
        user_name=user.name if user else entry.user_id,
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
        triage=TriageDecision.model_validate(entry.triage) if entry.triage else None,
        reviewed_by=entry.reviewed_by,
        created_at=entry.created_at,
        claim=claim_out(claim) if claim else None,
    )


async def list_entries(
    db: AsyncSession,
    segment_id: int | None = None,
    user_id: str | None = None,
    include_superseded: bool = False,
    limit: int = 200,
) -> list[EntryOut]:
    await get_clock(db)
    query = (
        select(DemandEntry, Claim)
        .outerjoin(Claim, Claim.entry_id == DemandEntry.id)
        .order_by(DemandEntry.created_at.desc(), DemandEntry.month.desc())
        .limit(limit)
    )
    if segment_id is not None:
        query = query.where(DemandEntry.segment_id == segment_id)
    if user_id is not None:
        query = query.where(DemandEntry.user_id == user_id)
    if not include_superseded:
        query = query.where(DemandEntry.status != "superseded")
    rows = (await db.execute(query)).all()
    segments = {s.id: s for s in (await db.execute(select(Segment))).scalars()}
    return [to_out(entry, claim, segments) for entry, claim in rows]
