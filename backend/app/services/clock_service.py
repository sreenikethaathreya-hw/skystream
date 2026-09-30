from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.decision_provider import get_decision_provider
from app.config import get_settings
from app.constants.demo import DEMO_USERS, MONTH_NAMES
from app.models import Claim, DemandEntry, MonthlyActual, MonthlyPlan, Segment
from app.models.base import utcnow
from app.schemas.api import AdvanceOut, ResolvedClaimOut
from app.services.context_service import get_clock, segment_label
from app.services.seed_service import seed_database
from app.services.track_record_service import recompute_track_records

NEUTRAL_BAND = 0.05


def numeric_support(direction: str, actual: float, plan: float) -> bool:
    if direction == "up":
        return actual >= plan
    if direction == "down":
        return actual < plan
    return plan > 0 and abs(actual - plan) / plan <= NEUTRAL_BAND


def resolve(supported: bool, probability: float) -> str:
    if supported and probability >= 0.5:
        return "confirmed"
    if not supported and probability < 0.5:
        return "contradicted"
    return "inconclusive"


async def advance_month(db: AsyncSession) -> AdvanceOut:
    clock = await get_clock(db)
    if clock.month >= 12:
        raise HTTPException(status_code=400, detail="The demo year is complete; reset to start again")
    closing = clock.month

    rows = (
        await db.execute(
            select(DemandEntry, Claim, MonthlyActual, MonthlyPlan, Segment)
            .join(Claim, Claim.entry_id == DemandEntry.id)
            .join(Segment, Segment.id == DemandEntry.segment_id)
            .join(
                MonthlyActual,
                (MonthlyActual.segment_id == DemandEntry.segment_id)
                & (MonthlyActual.year == DemandEntry.year)
                & (MonthlyActual.month == DemandEntry.month),
            )
            .join(
                MonthlyPlan,
                (MonthlyPlan.segment_id == DemandEntry.segment_id)
                & (MonthlyPlan.year == DemandEntry.year)
                & (MonthlyPlan.month == DemandEntry.month),
            )
            .where(
                Claim.resolution == "pending",
                Claim.check_year == clock.year,
                Claim.check_month == closing,
                DemandEntry.status != "superseded",
            )
        )
    ).all()

    provider = get_decision_provider()
    resolved: list[ResolvedClaimOut] = []
    for entry, claim, actual, plan, segment in rows:
        supported = numeric_support(claim.direction, actual.qty_ks, plan.qty_ks)
        change = (actual.qty_ks - plan.qty_ks) / plan.qty_ks if plan.qty_ks else 0.0
        evidence = (
            f"{MONTH_NAMES[closing - 1]} actual sales {actual.qty_ks:,.0f} KS vs plan {plan.qty_ks:,.0f} KS "
            f"({change:+.1%}). Rep entered {entry.value:,.0f} KS (range {entry.low:,.0f}-{entry.high:,.0f})."
        )
        claim_text = claim.summary or entry.justification or f"Demand {claim.direction} vs plan"
        probability, used = await provider.verify_claim(claim_text, evidence, supported)
        in_range = entry.low <= actual.qty_ks <= entry.high
        claim.resolution = resolve(supported, probability)
        claim.resolved_at = utcnow()
        claim.resolution_detail = {
            "actual": actual.qty_ks,
            "plan": plan.qty_ks,
            "inRange": in_range,
            "errorPct": (entry.value - actual.qty_ks) / actual.qty_ks if actual.qty_ks else None,
            "supportedProbability": probability,
            "numericSupport": supported,
            "provider": used,
            "evidence": evidence,
        }
        resolved.append(
            ResolvedClaimOut(
                entry_id=entry.id,
                segment_label=segment_label(segment),
                user_name=DEMO_USERS[entry.user_id].name if entry.user_id in DEMO_USERS else entry.user_id,
                resolution=claim.resolution,
                actual=actual.qty_ks,
                value=entry.value,
                in_range=in_range,
                supported_probability=probability,
                provider=used,
            )
        )

    clock.month = closing + 1
    await db.flush()
    await recompute_track_records(db)
    await db.commit()
    return AdvanceOut(
        from_month=closing,
        to_month=clock.month,
        resolved=resolved,
        confirmed=sum(r.resolution == "confirmed" for r in resolved),
        contradicted=sum(r.resolution == "contradicted" for r in resolved),
        inconclusive=sum(r.resolution == "inconclusive" for r in resolved),
    )


async def reset_demo(db: AsyncSession) -> None:
    await seed_database(db, get_settings().seed_dir)
