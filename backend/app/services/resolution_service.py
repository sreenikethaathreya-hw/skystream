"""Resolve pending claims once a month's actual sales are known (demo: Advance month; real: actuals upload)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.decision_provider import DecisionPolicy, get_decision_provider
from app.constants.demo import MONTH_NAMES
from app.models import Claim, DemandEntry, MonthlyActual, MonthlyPlan, Segment
from app.models.base import utcnow
from app.schemas.api import ResolvedClaimOut
from app.services.context_service import segment_label
from app.services.user_service import user_names

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


async def resolve_month(
    db: AsyncSession, year: int, month: int, policy: DecisionPolicy, country_code: str | None = None
) -> list[ResolvedClaimOut]:
    query = (
        select(DemandEntry, Claim, MonthlyActual, MonthlyPlan, Segment)
        .join(Claim, Claim.entry_id == DemandEntry.id)
        .join(Segment, Segment.id == DemandEntry.segment_id)
        .join(
            MonthlyActual,
            (MonthlyActual.country_code == DemandEntry.country_code)
            & (MonthlyActual.segment_id == DemandEntry.segment_id)
            & (MonthlyActual.year == DemandEntry.year)
            & (MonthlyActual.month == DemandEntry.month),
        )
        .join(
            MonthlyPlan,
            (MonthlyPlan.country_code == DemandEntry.country_code)
            & (MonthlyPlan.segment_id == DemandEntry.segment_id)
            & (MonthlyPlan.year == DemandEntry.year)
            & (MonthlyPlan.month == DemandEntry.month),
        )
        .where(
            Claim.resolution == "pending",
            Claim.check_year == year,
            Claim.check_month == month,
            DemandEntry.status != "superseded",
        )
    )
    if country_code is not None:
        query = query.where(DemandEntry.country_code == country_code)
    rows = (await db.execute(query)).all()

    provider = get_decision_provider()
    names = await user_names(db)
    resolved: list[ResolvedClaimOut] = []
    for entry, claim, actual, plan, segment in rows:
        supported = numeric_support(claim.direction, actual.qty_ks, plan.qty_ks)
        change = (actual.qty_ks - plan.qty_ks) / plan.qty_ks if plan.qty_ks else 0.0
        evidence = (
            f"{MONTH_NAMES[month - 1]} actual sales {actual.qty_ks:,.0f} KS vs plan {plan.qty_ks:,.0f} KS "
            f"({change:+.1%}). Rep entered {entry.value:,.0f} KS (range {entry.low:,.0f}-{entry.high:,.0f})."
        )
        claim_text = claim.summary or entry.justification or f"Demand {claim.direction} vs plan"
        probability, used = await provider.verify_claim(claim_text, evidence, supported, policy)
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
                segment_label=f"{entry.country_code} {segment_label(segment)}",
                user_name=names.get(entry.user_id, entry.user_id),
                resolution=claim.resolution,
                actual=actual.qty_ks,
                value=entry.value,
                in_range=in_range,
                supported_probability=probability,
                provider=used,
            )
        )
    await db.flush()
    return resolved
