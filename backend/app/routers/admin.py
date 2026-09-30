from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.ingest.templates import TEMPLATES, template_csv
from app.middleware.auth import get_current_user, require_role
from app.schemas.api import BatchOut, UploadKindOut, UserAdminIn, UserAdminOut
from app.services import upload_service, user_service
from app.services.settings_service import AppSettings, AppSettingsPatch, get_app_settings, update_app_settings
from app.services.user_service import CurrentUser

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def admin_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    require_role(user, "admin")
    return user


@router.get("/upload-kinds", response_model=list[UploadKindOut])
async def upload_kinds(db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(admin_user)):
    return await upload_service.list_kinds(db)


@router.post("/uploads", response_model=BatchOut, status_code=201)
async def upload(
    kind: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(admin_user),
) -> BatchOut:
    return await upload_service.preview(db, user, kind, file.filename or "upload", await file.read())


@router.get("/uploads", response_model=list[BatchOut])
async def uploads(db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(admin_user)):
    return await upload_service.history(db)


@router.post("/uploads/{batch_id}/commit", response_model=BatchOut)
async def commit(batch_id: str, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(admin_user)):
    return await upload_service.commit(db, batch_id)


@router.post("/uploads/{batch_id}/discard", response_model=BatchOut)
async def discard(batch_id: str, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(admin_user)):
    return await upload_service.discard(db, batch_id)


@router.get("/templates/{kind}.csv", response_class=PlainTextResponse)
async def template(kind: str, _: CurrentUser = Depends(admin_user)) -> PlainTextResponse:
    if kind not in TEMPLATES:
        raise HTTPException(status_code=404, detail="No template for this kind")
    return PlainTextResponse(
        template_csv(kind),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{kind}-template.csv"'},
    )


@router.get("/users", response_model=list[UserAdminOut])
async def users(db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(admin_user)):
    return await user_service.list_users(db)


@router.put("/users", response_model=list[UserAdminOut])
async def save_user(
    body: UserAdminIn, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(admin_user)
):
    if body.email.lower() == user.id and (body.role != "admin" or not body.active):
        raise HTTPException(status_code=400, detail="You cannot remove your own admin access")
    await user_service.upsert_user(db, body.email, body.name, body.role, body.scopes, body.active)
    await db.commit()
    return await user_service.list_users(db)


@router.get("/settings", response_model=AppSettings)
async def settings(db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(admin_user)):
    return await get_app_settings(db)


@router.put("/settings", response_model=AppSettings)
async def save_settings(
    body: AppSettingsPatch, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(admin_user)
) -> AppSettings:
    return await update_app_settings(db, body, user.id)
