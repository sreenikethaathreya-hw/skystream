from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, DemandEntry, MonthlyActual, RepTrackRecord
from app.models.base import utcnow

RESOLVED = ("confirmed", "contradicted", "inconclusive")


@dataclass
class _Stats:
    errors: list[float] = field(default_factory=list)
    covered: list[float] = field(default_factory=list)
    confirmed: int = 0
    contradicted: int = 0


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


async def recompute_track_records(db: AsyncSession) -> None:
    rows = (
        await db.execute(
            select(DemandEntry, Claim, MonthlyActual)
            .join(Claim, Claim.entry_id == DemandEntry.id)
            .join(
                MonthlyActual,
                (MonthlyActual.segment_id == DemandEntry.segment_id)
                & (MonthlyActual.year == DemandEntry.year)
                & (MonthlyActual.month == DemandEntry.month),
            )
            .where(Claim.resolution.in_(RESOLVED))
        )
    ).all()

    stats: dict[str, _Stats] = defaultdict(_Stats)
    for entry, claim, actual in rows:
        s = stats[entry.user_id]
        if actual.qty_ks > 0:
            s.errors.append((entry.value - actual.qty_ks) / actual.qty_ks)
        s.covered.append(1.0 if entry.low <= actual.qty_ks <= entry.high else 0.0)
        if claim.resolution == "confirmed":
            s.confirmed += 1
        elif claim.resolution == "contradicted":
            s.contradicted += 1

    existing = {r.user_id: r for r in (await db.execute(select(RepTrackRecord))).scalars()}
    for user_id, s in stats.items():
        record = existing.get(user_id) or RepTrackRecord(user_id=user_id)
        judged = s.confirmed + s.contradicted
        record.entries_resolved = len(s.covered)
        record.bias_pct = _mean(s.errors)
        record.range_coverage = _mean(s.covered)
        record.confirmed = s.confirmed
        record.contradicted = s.contradicted
        record.claim_hit_rate = s.confirmed / judged if judged else None
        record.updated_at = utcnow()
        db.add(record)
    await db.flush()
