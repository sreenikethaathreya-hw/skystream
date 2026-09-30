"""Demo-mode clock. Real mode closes months by uploading actuals (see ingest.commit)."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.decision_provider import decision_policy
from app.config import get_settings
from app.models import DemoClock
from app.schemas.api import AdvanceOut
from app.services.resolution_service import resolve_month
from app.services.seed_service import seed_database
from app.services.settings_service import get_app_settings
from app.services.track_record_service import recompute_track_records


async def get_demo_clock(db: AsyncSession) -> DemoClock:
    clock = await db.get(DemoClock, 1)
    if clock is None:
        raise HTTPException(status_code=503, detail="Demo data is not seeded")
    return clock


async def advance_month(db: AsyncSession) -> AdvanceOut:
    if not get_settings().is_demo:
        raise HTTPException(status_code=400, detail="Months close when actuals are uploaded")
    clock = await get_demo_clock(db)
    if clock.month >= 12:
        raise HTTPException(status_code=400, detail="The demo year is complete; reset to start again")
    closing = clock.month
    resolved = await resolve_month(db, clock.year, closing, decision_policy(await get_app_settings(db)))
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
    if not get_settings().is_demo:
        raise HTTPException(status_code=400, detail="Reset is only available in demo mode")
    await seed_database(db, get_settings().seed_dir)
