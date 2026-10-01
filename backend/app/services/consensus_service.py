from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.decision_provider import decision_policy, get_decision_provider
from app.constants.demo import MONTH_NAMES
from app.models import Claim, CompetitorShare, DemandEntry, MarketYear, PlanYear, Segment
from app.models.base import utcnow
from app.schemas.api import EntryOut, QueueItemOut, QueueOut, RtbOut
from app.services.context_service import COMMITTED_SOURCES, current_period, segment_label
from app.services.entry_service import scope_filter, to_out
from app.services.note_service import attach_notes
from app.services.rep_service import is_weak, track_records
from app.services.settings_service import get_app_settings
from app.services.user_service import UNASSIGNED, CurrentUser, user_names

OPEN_STATUSES = ("submitted", "discuss", "challenged", "needs_justification")
DECISION_STATUS = {"approve": "approved", "discuss": "discuss", "challenge": "challenged"}


def exception_reasons(entry: DemandEntry, claim: Claim | None, weak_rep: bool, rep_name: str) -> list[str]:
    reasons = [f["message"] for f in entry.flags or []]
    if weak_rep:
        reasons.append(f"{rep_name} has a weak track record")
    if claim is not None:
        if claim.specificity is not None and claim.specificity < 1.5:
            reasons.append("Justification is vague")
        if claim.addresses_flags is not None and claim.addresses_flags < 0.5:
            reasons.append("Justification does not address the flags")
    if entry.status == "needs_justification":
        reasons.append("Flagged IBP number waiting for the rep's justification")
    if entry.user_id == UNASSIGNED:
        reasons.append("IBP number with no rep assigned to this segment")
    if entry.status == "discuss":
        reasons.append("Marked for discussion")
    if entry.status == "challenged":
        reasons.append("Challenged, waiting on the rep")
    return reasons


async def _open_entries(db: AsyncSession, country: str | None, mega: str | None):
    query = (
        select(DemandEntry, Claim)
        .outerjoin(Claim, Claim.entry_id == DemandEntry.id)
        .where(DemandEntry.source.in_(COMMITTED_SOURCES), DemandEntry.status.in_(OPEN_STATUSES))
        .order_by(DemandEntry.country_code, DemandEntry.segment_id, DemandEntry.month)
    )
    return [(entry, claim) for entry, claim in (await db.execute(scope_filter(query, country, mega))).all()]


async def build_queue(db: AsyncSession, country: str | None = None, mega: str | None = None) -> QueueOut:
    records = await track_records(db)
    segments = {s.id: s for s in (await db.execute(select(Segment))).scalars()}
    names = await user_names(db)
    policy = decision_policy(await get_app_settings(db))
    provider = get_decision_provider()
    exceptions: list[QueueItemOut] = []
    routine: list[EntryOut] = []
    for entry, claim in await _open_entries(db, country, mega):
        weak = is_weak(records.get(entry.user_id))
        reasons = exception_reasons(entry, claim, weak, names.get(entry.user_id, entry.user_id))
        if not reasons:
            routine.append(to_out(entry, claim, segments, names))
            continue
        if entry.triage is None:
            severities = {f["severity"] for f in entry.flags or []}
            text = (
                f"{entry.country_code} {segment_label(segments[entry.segment_id])} {MONTH_NAMES[entry.month - 1]}: "
                f"{entry.value:,.0f} KS. Justification: {entry.justification or 'none'}. "
                f"Concerns: {'; '.join(reasons)}"
            )
            decision = await provider.triage(
                text,
                has_critical="critical" in severities,
                has_warning="warning" in severities,
                weak_record=weak,
                specificity=claim.specificity if claim and claim.specificity is not None else 0.0,
                policy=policy,
            )
            entry.triage = decision.model_dump(by_alias=True)
        exceptions.append(QueueItemOut(entry=to_out(entry, claim, segments, names), reasons=reasons))
    await db.commit()
    await attach_notes(db, [item.entry for item in exceptions] + routine)
    return QueueOut(exceptions=exceptions, routine=routine)


async def bulk_approve(
    db: AsyncSession, user: CurrentUser, country: str | None = None, mega: str | None = None
) -> int:
    queue = await build_queue(db, country, mega)
    ids = [e.id for e in queue.routine]
    for entry_id in ids:
        entry = await db.get(DemandEntry, entry_id)
        if entry:
            entry.status, entry.reviewed_by, entry.reviewed_at = "approved", user.id, utcnow()
    await db.commit()
    return len(ids)


async def decide(db: AsyncSession, user: CurrentUser, entry_id: str, decision: str) -> None:
    entry = await db.get(DemandEntry, entry_id)
    if entry is None or entry.source not in COMMITTED_SOURCES:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status == "superseded":
        raise HTTPException(status_code=409, detail="A newer entry replaced this one")
    entry.status, entry.reviewed_by, entry.reviewed_at = DECISION_STATUS[decision], user.id, utcnow()
    await db.commit()


async def draft_rtb(db: AsyncSession, country_code: str, segment_id: int) -> RtbOut:
    period = await current_period(db, country_code)
    segment = await db.get(Segment, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Unknown micro-segment")
    year = period.year
    market = {
        m.year: m
        for m in (
            await db.execute(
                select(MarketYear).where(
                    MarketYear.country_code == country_code, MarketYear.segment_id == segment_id
                )
            )
        ).scalars()
    }
    plan = (
        await db.execute(
            select(PlanYear).where(
                PlanYear.country_code == country_code,
                PlanYear.segment_id == segment_id,
                PlanYear.year == year,
            )
        )
    ).scalar_one_or_none()
    confirmed = (
        await db.execute(
            select(DemandEntry, Claim)
            .join(Claim, Claim.entry_id == DemandEntry.id)
            .where(
                DemandEntry.country_code == country_code,
                DemandEntry.segment_id == segment_id,
                Claim.resolution == "confirmed",
            )
            .order_by(DemandEntry.month.desc())
            .limit(5)
        )
    ).all()
    competitors = (
        (
            await db.execute(
                select(CompetitorShare)
                .where(
                    CompetitorShare.country_code == country_code,
                    CompetitorShare.mega_segment_id == segment.mega_segment_id,
                    CompetitorShare.year == year,
                    CompetitorShare.competitor.notin_(["Others"]),
                )
                .order_by(CompetitorShare.share_pct.desc())
                .limit(4)
            )
        )
        .scalars()
        .all()
    )
    names = await user_names(db)

    now, before = market.get(year), market.get(year - 1)
    area_trend = (
        (now.hectares - before.hectares) / before.hectares if now and before and before.hectares else 0.0
    )
    share = plan.qty_ks / now.qty_ks if plan and now and now.qty_ks else 0.0
    label = f"{country_code} {segment_label(segment)}"
    evidence = [
        f"{MONTH_NAMES[e.month - 1]} ({names.get(e.user_id, e.user_id)}): {e.justification}"
        for e, _ in confirmed
    ]
    comp_line = ", ".join(
        f"{c.competitor} {c.share_pct:.0f}% ({(c.trend or 'n/a').lower()})" for c in competitors
    )
    dynamics = (now.notes or {}).get("dynamics") if now else None

    fallback = "\n".join(
        [
            f"Reasons to believe: {label}",
            f"- Market: {now.hectares:,.0f} ha in {year} ({area_trend:+.1%} vs {year - 1}); "
            f"Syngenta plan {plan.qty_ks if plan else 0:,.0f} KS, {share:.1%} volume share."
            if now
            else "- Market: n/a",
            f"- Confirmed field evidence ({len(evidence)}): " + ("; ".join(evidence[:3]) or "none yet"),
            f"- Competitive context: {comp_line or 'no competitor data'}.",
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
