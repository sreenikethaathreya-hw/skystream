from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.demo import DEMO_USERS, WEAK_BIAS, WEAK_HIT_RATE
from app.models import RepTrackRecord
from app.schemas.api import TrackRecordOut, UserOut


def is_weak(record: RepTrackRecord | None) -> bool:
    if record is None:
        return False
    weak_hits = record.claim_hit_rate is not None and record.claim_hit_rate < WEAK_HIT_RATE
    weak_bias = record.bias_pct is not None and abs(record.bias_pct) > WEAK_BIAS
    return weak_hits or weak_bias


async def track_records(db: AsyncSession) -> dict[str, RepTrackRecord]:
    return {r.user_id: r for r in (await db.execute(select(RepTrackRecord))).scalars()}


async def list_track_records(db: AsyncSession) -> list[TrackRecordOut]:
    records = await track_records(db)
    out = []
    for user in DEMO_USERS.values():
        if user.role != "rep":
            continue
        r = records.get(user.id)
        out.append(
            TrackRecordOut(
                user=UserOut.model_validate(user),
                entries_resolved=r.entries_resolved if r else 0,
                bias_pct=r.bias_pct if r else None,
                claim_hit_rate=r.claim_hit_rate if r else None,
                range_coverage=r.range_coverage if r else None,
                confirmed=r.confirmed if r else 0,
                contradicted=r.contradicted if r else 0,
                weak=is_weak(r),
            )
        )
    return out
