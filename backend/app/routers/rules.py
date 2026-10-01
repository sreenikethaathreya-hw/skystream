from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user, require_role
from app.schemas.rules import RuleCompileIn, RuleCreateIn, RuleDraftOut, RuleOut
from app.services import rule_service
from app.services.user_service import CurrentUser

router = APIRouter(prefix="/api/rules", tags=["rules"], dependencies=[Depends(get_current_user)])
AUTHORS = ("lead", "admin")


@router.get("", response_model=list[RuleOut])
async def list_rules(
    country: str = Query(min_length=2, max_length=2),
    mega: str = Query(min_length=1, max_length=10),
    db: AsyncSession = Depends(get_db),
) -> list[RuleOut]:
    return await rule_service.list_rules(db, country.upper(), mega)


@router.post("/compile", response_model=RuleDraftOut)
async def compile_rule(
    body: RuleCompileIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RuleDraftOut:
    require_role(user, *AUTHORS)
    return await rule_service.compile_rule(db, body)


@router.post("", response_model=RuleOut, status_code=201)
async def create_rule(
    body: RuleCreateIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RuleOut:
    require_role(user, *AUTHORS)
    return await rule_service.create_rule(db, user, body)


@router.post("/{rule_id}/retire", status_code=204)
async def retire_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    require_role(user, *AUTHORS)
    await rule_service.retire_rule(db, user, rule_id)
