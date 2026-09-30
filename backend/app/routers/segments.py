from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.api import CubeOut
from app.services.context_service import build_cube

router = APIRouter(prefix="/api/segments", tags=["segments"])


@router.get("/cube", response_model=CubeOut)
async def cube(db: AsyncSession = Depends(get_db)) -> CubeOut:
    return await build_cube(db)
