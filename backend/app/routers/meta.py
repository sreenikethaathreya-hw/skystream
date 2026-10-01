from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.data_agent.runtime import get_runtime
from app.ai.decision_provider import get_decision_provider
from app.config import get_settings
from app.constants.demo import DEMO_USERS
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import DemoClock
from app.schemas.api import ClockOut, ConfigOut, FirebaseConfigOut, MetaOut, ScopeOptionOut, UserOut
from app.services import export_service
from app.services.context_service import scope_options
from app.services.settings_service import get_app_settings
from app.services.user_service import CurrentUser, touch

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config", response_model=ConfigOut)
async def config() -> ConfigOut:
    """Public: tells the SPA which mode it is in and how to start Firebase sign-in."""
    settings = get_settings()
    firebase = None
    if not settings.is_demo and settings.firebase_web_api_key and settings.firebase_project_id:
        firebase = FirebaseConfigOut(
            api_key=settings.firebase_web_api_key,
            auth_domain=settings.firebase_auth_domain or f"{settings.firebase_project_id}.firebaseapp.com",
            project_id=settings.firebase_project_id,
        )
    return ConfigOut(data_mode=settings.data_mode, firebase=firebase)


@router.get("/meta", response_model=MetaOut)
async def meta(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> MetaOut:
    settings = get_settings()
    app_settings = await get_app_settings(db)
    clock = await db.get(DemoClock, 1) if settings.is_demo else None
    if not settings.is_demo:
        await touch(db, user.id)
    provider = get_decision_provider()
    status = provider.status()
    chat = {
        "chatEnabled": settings.chat_enabled and get_runtime() is not None,
        "chatMode": "agent" if status["geminiConfigured"] else "templates",
    }
    return MetaOut(
        data_mode=settings.data_mode,
        me=UserOut(id=user.id, name=user.name, role=user.role, title=user.title),
        users=[UserOut.model_validate(u) for u in DEMO_USERS.values()] if settings.is_demo else [],
        clock=ClockOut(year=clock.year, month=clock.month) if clock else None,
        ai={
            **status,
            **chat,
            "externalAiAllowed": app_settings.external_ai_allowed,
            "chatWritesAllowed": app_settings.chat_writes_allowed and chat["chatMode"] == "agent",
        },
        thresholds=app_settings.thresholds,
        reporting_currency=app_settings.reporting_currency,
        default_display_currency=app_settings.default_display_currency,
    )


@router.get("/scopes", response_model=list[ScopeOptionOut])
async def scopes(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    return await scope_options(db, user)


@router.get("/data-quality")
async def data_quality(
    db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(get_current_user)
) -> dict:
    return await export_service.data_quality(db)
