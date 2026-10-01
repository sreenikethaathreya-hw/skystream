from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.api import AnalyzeOut, EntryIn, EntryOut, JustifyIn, NoteIn, NoteOut
from app.services import entry_service, note_service
from app.services.user_service import CurrentUser

router = APIRouter(prefix="/api", tags=["entries"], dependencies=[Depends(get_current_user)])


@router.post("/justifications/analyze", response_model=AnalyzeOut)
async def analyze(body: EntryIn, db: AsyncSession = Depends(get_db)) -> AnalyzeOut:
    return await entry_service.analyze(db, body)


@router.post("/entries", response_model=EntryOut, status_code=201)
async def create_entry(
    body: EntryIn,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EntryOut:
    entry = await entry_service.create_entry(db, user, body)
    if entry.claim:
        background.add_task(entry_service.polish_claim_summary, entry.id)
    return entry


@router.post("/entries/{entry_id}/justify", response_model=EntryOut)
async def justify_entry(
    entry_id: str,
    body: JustifyIn,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EntryOut:
    entry = await entry_service.justify_entry(db, user, entry_id, body)
    if entry.claim:
        background.add_task(entry_service.polish_claim_summary, entry.id)
    return entry


@router.get("/entries", response_model=list[EntryOut])
async def list_entries(
    country: str | None = Query(default=None, max_length=2),
    mega: str | None = Query(default=None, max_length=10),
    segment_id: int | None = Query(default=None, alias="segmentId"),
    user_id: str | None = Query(default=None, alias="userId"),
    include_superseded: bool = Query(default=False, alias="includeSuperseded"),
    limit: int = Query(default=200, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[EntryOut]:
    entries = await entry_service.list_entries(db, country, mega, segment_id, user_id, include_superseded, limit)
    return await note_service.attach_notes(db, entries)


@router.get("/entries/{entry_id}/notes", response_model=list[NoteOut])
async def list_notes(entry_id: str, db: AsyncSession = Depends(get_db)) -> list[NoteOut]:
    return await note_service.list_notes(db, entry_id)


@router.post("/entries/{entry_id}/notes", response_model=NoteOut, status_code=201)
async def add_note(
    entry_id: str,
    body: NoteIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> NoteOut:
    return await note_service.add_note(db, user, entry_id, body.body)
