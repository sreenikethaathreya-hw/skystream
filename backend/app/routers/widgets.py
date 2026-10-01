from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.widgets import (
    UserWidgetIn,
    UserWidgetOut,
    UserWidgetRename,
    WidgetPrefsIn,
    WidgetPrefsOut,
    WidgetRunOut,
    WidgetsOut,
)
from app.services import widget_service
from app.services.user_service import CurrentUser

router = APIRouter(prefix="/api/me/widgets", tags=["widgets"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=WidgetsOut)
async def get_widgets(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> WidgetsOut:
    return await widget_service.get_widgets(db, user)


@router.put("/prefs", response_model=WidgetPrefsOut)
async def set_prefs(
    body: WidgetPrefsIn, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
) -> WidgetPrefsOut:
    return await widget_service.set_prefs(db, user, body)


@router.post("", response_model=UserWidgetOut, status_code=201)
async def create_widget(
    body: UserWidgetIn, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
) -> UserWidgetOut:
    return await widget_service.create_widget(db, user, body)


@router.put("/{widget_id}", response_model=UserWidgetOut)
async def rename_widget(
    widget_id: int,
    body: UserWidgetRename,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> UserWidgetOut:
    return await widget_service.rename_widget(db, user, widget_id, body.title)


@router.delete("/{widget_id}", status_code=204)
async def delete_widget(
    widget_id: int, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
) -> None:
    await widget_service.delete_widget(db, user, widget_id)


@router.get("/{widget_id}/run", response_model=WidgetRunOut)
async def run_widget(
    widget_id: int, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
) -> WidgetRunOut:
    return await widget_service.run_widget(db, user, widget_id)
