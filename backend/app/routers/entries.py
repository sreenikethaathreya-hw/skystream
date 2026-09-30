from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.demo import DemoUser
from app.database import get_db
from app.middleware.demo_user import get_current_user
from app.schemas.api import AnalyzeOut, EntryIn, EntryOut
from app.services import entry_service

router = APIRouter(prefix="/api", tags=["entries"])


@router.post("/justifications/analyze", response_model=AnalyzeOut)
async def analyze(body: EntryIn, db: AsyncSession = Depends(get_db)) -> AnalyzeOut:
    return await entry_service.analyze(db, body)


@router.post("/entries", response_model=EntryOut, status_code=201)
async def create_entry(
    body: EntryIn,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: DemoUser = Depends(get_current_user),
) -> EntryOut:
    entry = await entry_service.create_entry(db, user, body)
    if entry.claim:
        background.add_task(entry_service.polish_claim_summary, entry.id)
    return entry


@router.get("/entries", response_model=list[EntryOut])
async def list_entries(
    segment_id: int | None = Query(default=None, alias="segmentId"),
    user_id: str | None = Query(default=None, alias="userId"),
    include_superseded: bool = Query(default=False, alias="includeSuperseded"),
    limit: int = Query(default=200, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[EntryOut]:
    return await entry_service.list_entries(db, segment_id, user_id, include_superseded, limit)
