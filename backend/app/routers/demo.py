from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.api import AdvanceOut, TrackRecordOut
from app.services import chat_service, clock_service, rep_service

router = APIRouter(prefix="/api", tags=["demo"], dependencies=[Depends(get_current_user)])


@router.post("/demo/advance", response_model=AdvanceOut)
async def advance(db: AsyncSession = Depends(get_db)) -> AdvanceOut:
    return await clock_service.advance_month(db)


@router.post("/demo/reset", status_code=204)
async def reset(db: AsyncSession = Depends(get_db)) -> None:
    await clock_service.reset_demo(db)
    await chat_service.delete_all_sessions()


@router.get("/reps", response_model=list[TrackRecordOut])
async def reps(db: AsyncSession = Depends(get_db)) -> list[TrackRecordOut]:
    return await rep_service.list_track_records(db)
