from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.api import CubeOut
from app.services.context_service import build_cube
from app.services.user_service import CurrentUser

router = APIRouter(prefix="/api/segments", tags=["segments"])


@router.get("/cube", response_model=CubeOut)
async def cube(
    country: str | None = Query(default=None, min_length=2, max_length=2),
    mega: str | None = Query(default=None, max_length=10),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> CubeOut:
    return await build_cube(db, user, country, mega)
