from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.demo import DemoUser
from app.database import get_db
from app.middleware.demo_user import get_current_user, require_role
from app.schemas.api import DecisionIn, QueueOut, RtbIn, RtbOut
from app.services import consensus_service, export_service

router = APIRouter(prefix="/api", tags=["consensus"])


@router.get("/consensus/queue", response_model=QueueOut)
async def queue(db: AsyncSession = Depends(get_db)) -> QueueOut:
    return await consensus_service.build_queue(db)


@router.post("/consensus/bulk-approve")
async def bulk_approve(
    db: AsyncSession = Depends(get_db), user: DemoUser = Depends(get_current_user)
) -> dict[str, int]:
    require_role(user, "lead")
    return {"approved": await consensus_service.bulk_approve(db, user)}


@router.post("/consensus/entries/{entry_id}/decision", status_code=204)
async def decide(
    entry_id: str,
    body: DecisionIn,
    db: AsyncSession = Depends(get_db),
    user: DemoUser = Depends(get_current_user),
) -> None:
    require_role(user, "lead")
    await consensus_service.decide(db, user, entry_id, body.decision)


@router.post("/consensus/rtb", response_model=RtbOut)
async def rtb(body: RtbIn, db: AsyncSession = Depends(get_db)) -> RtbOut:
    return await consensus_service.draft_rtb(db, body.segment_id)


@router.get("/export/supply.csv", response_class=PlainTextResponse)
async def supply_csv(db: AsyncSession = Depends(get_db)) -> PlainTextResponse:
    return PlainTextResponse(
        await export_service.supply_csv(db),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="supply-handoff.csv"'},
    )
