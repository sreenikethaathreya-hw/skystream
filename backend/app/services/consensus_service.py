from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.decision_provider import get_decision_provider
from app.constants.demo import DEMO_USERS, MONTH_NAMES, DemoUser
from app.models import Claim, CompetitorShare, DemandEntry, MarketYear, PlanYear, Segment
from app.models.base import utcnow
from app.schemas.api import EntryOut, QueueItemOut, QueueOut, RtbOut
from app.services.context_service import get_clock, segment_label
from app.services.entry_service import to_out
from app.services.rep_service import is_weak, track_records

OPEN_STATUSES = ("submitted", "discuss", "challenged")
DECISION_STATUS = {"approve": "approved", "discuss": "discuss", "challenge": "challenged"}


def exception_reasons(entry: DemandEntry, claim: Claim | None, weak_rep: bool) -> list[str]:
    reasons = [f["message"] for f in entry.flags or []]
    user = DEMO_USERS.get(entry.user_id)
    if weak_rep:
        reasons.append(f"{user.name if user else entry.user_id} has a weak track record")
    if claim is not None:
        if claim.specificity is not None and claim.specificity < 1.5:
            reasons.append("Justification is vague")
        if claim.addresses_flags is not None and claim.addresses_flags < 0.5:
            reasons.append("Justification does not address the flags")
    if entry.status == "discuss":
        reasons.append("Marked for discussion")
    if entry.status == "challenged":
        reasons.append("Challenged, waiting on the rep")
    return reasons


async def _open_entries(db: AsyncSession) -> list[tuple[DemandEntry, Claim | None]]:
    rows = await db.execute(
        select(DemandEntry, Claim)
        .outerjoin(Claim, Claim.entry_id == DemandEntry.id)
        .where(DemandEntry.source == "live", DemandEntry.status.in_(OPEN_STATUSES))
        .order_by(DemandEntry.segment_id, DemandEntry.month)
    )
    return [(entry, claim) for entry, claim in rows.all()]


async def build_queue(db: AsyncSession) -> QueueOut:
    await get_clock(db)
    records = await track_records(db)
    segments = {s.id: s for s in (await db.execute(select(Segment))).scalars()}
    provider = get_decision_provider()
    exceptions: list[QueueItemOut] = []
    routine: list[EntryOut] = []
    for entry, claim in await _open_entries(db):
        weak = is_weak(records.get(entry.user_id))
        reasons = exception_reasons(entry, claim, weak)
        if not reasons:
            routine.append(to_out(entry, claim, segments))
            continue
        if entry.triage is None:
            severities = {f["severity"] for f in entry.flags or []}
            text = (
                f"{segment_label(segments[entry.segment_id])} {MONTH_NAMES[entry.month - 1]}: "
                f"{entry.value:,.0f} KS. Justification: {entry.justification or 'none'}. "
                f"Concerns: {'; '.join(reasons)}"
            )
            decision = await provider.triage(
                text,
                has_critical="critical" in severities,
                has_warning="warning" in severities,
                weak_record=weak,
                specificity=claim.specificity if claim and claim.specificity is not None else 0.0,
            )
            entry.triage = decision.model_dump(by_alias=True)
        exceptions.append(QueueItemOut(entry=to_out(entry, claim, segments), reasons=reasons))
    await db.commit()
    return QueueOut(exceptions=exceptions, routine=routine)


async def bulk_approve(db: AsyncSession, user: DemoUser) -> int:
    queue = await build_queue(db)
    ids = [e.id for e in queue.routine]
    for entry_id in ids:
        entry = await db.get(DemandEntry, entry_id)
        if entry:
            entry.status, entry.reviewed_by, entry.reviewed_at = "approved", user.id, utcnow()
    await db.commit()
    return len(ids)


async def decide(db: AsyncSession, user: DemoUser, entry_id: str, decision: str) -> None:
    entry = await db.get(DemandEntry, entry_id)
    if entry is None or entry.source != "live":
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status == "superseded":
        raise HTTPException(status_code=409, detail="A newer entry replaced this one")
    entry.status, entry.reviewed_by, entry.reviewed_at = DECISION_STATUS[decision], user.id, utcnow()
    await db.commit()


async def draft_rtb(db: AsyncSession, segment_id: int) -> RtbOut:
    clock = await get_clock(db)
    segment = await db.get(Segment, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not in the locked scope")
    market = {
        m.year: m
        for m in (await db.execute(select(MarketYear).where(MarketYear.segment_id == segment_id))).scalars()
    }
    plan = (
        await db.execute(
            select(PlanYear).where(PlanYear.segment_id == segment_id, PlanYear.year == clock.year)
        )
    ).scalar_one_or_none()
    confirmed = (
        await db.execute(
            select(DemandEntry, Claim)
            .join(Claim, Claim.entry_id == DemandEntry.id)
            .where(DemandEntry.segment_id == segment_id, Claim.resolution == "confirmed")
            .order_by(DemandEntry.month.desc())
            .limit(5)
        )
    ).all()
    competitors = (
        (
            await db.execute(
                select(CompetitorShare)
                .where(CompetitorShare.year == clock.year, CompetitorShare.competitor.notin_(["Others"]))
                .order_by(CompetitorShare.share_pct.desc())
                .limit(4)
            )
        )
        .scalars()
        .all()
    )

    now, before = market.get(clock.year), market.get(clock.year - 1)
    area_trend = (
        (now.hectares - before.hectares) / before.hectares if now and before and before.hectares else 0.0
    )
    share = plan.qty_ks / now.qty_ks if plan and now and now.qty_ks else 0.0
    label = segment_label(segment)
    evidence = [
        f"{MONTH_NAMES[e.month - 1]} ({DEMO_USERS[e.user_id].name if e.user_id in DEMO_USERS else e.user_id}): "
        f"{e.justification}"
        for e, _ in confirmed
    ]
    comp_line = ", ".join(
        f"{c.competitor} {c.share_pct:.0f}% ({(c.trend or 'n/a').lower()})" for c in competitors
    )
    dynamics = (now.notes or {}).get("dynamics") if now else None

    fallback = "\n".join(
        [
            f"Reasons to believe: {label}",
            f"- Market: {now.hectares:,.0f} ha in {clock.year} ({area_trend:+.1%} vs {clock.year - 1}); "
            f"Syngenta plan {plan.qty_ks if plan else 0:,.0f} KS, {share:.1%} volume share."
            if now
            else "- Market: n/a",
            f"- Confirmed field evidence ({len(evidence)}): " + ("; ".join(evidence[:3]) or "none yet"),
            f"- Competitive context: {comp_line}.",
            f"- Watch: {dynamics}" if dynamics else "- Watch: no market dynamics note",
        ]
    )
    prompt = (
        "Draft a short reasons-to-believe narrative for a seed demand consensus meeting. "
        "Use only the facts below; cite the confirmed evidence; do not invent numbers.\n" + fallback
    )
    text, provider = await get_decision_provider().write_prose(prompt, fallback)
    return RtbOut(
        segment_id=segment_id, text=text, provider=provider, cited_entry_ids=[e.id for e, _ in confirmed]
    )
