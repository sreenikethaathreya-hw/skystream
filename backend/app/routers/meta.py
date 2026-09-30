from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.decision_provider import get_decision_provider
from app.config import get_settings
from app.constants.demo import DEMO_USERS
from app.database import get_db
from app.schemas.api import ClockOut, MetaOut, UserOut
from app.schemas.demand_math import Thresholds
from app.services.context_service import get_clock
from app.services.export_service import ingest_report
from app.services.seed_service import read_seed

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta", response_model=MetaOut)
async def meta(db: AsyncSession = Depends(get_db)) -> MetaOut:
    clock = await get_clock(db)
    scope = read_seed(get_settings().seed_dir, "meta")
    return MetaOut(
        country=scope["country"],
        species=scope["species"],
        mega_segment_id=scope["megaSegmentId"],
        mega_segment_desc=scope["megaSegmentDesc"],
        users=[UserOut.model_validate(u) for u in DEMO_USERS.values()],
        clock=ClockOut(year=clock.year, month=clock.month),
        ai=get_decision_provider().status(),
        thresholds=Thresholds(),
    )


@router.get("/data-quality")
async def data_quality() -> dict:
    return ingest_report()
