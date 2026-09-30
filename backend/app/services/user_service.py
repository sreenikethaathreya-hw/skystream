"""Who the caller is, what they cover, and display names for any user id."""

from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants.demo import DEMO_USERS
from app.models import AppUser, Segment, UserScope
from app.models.base import utcnow
from app.schemas.api import ScopeIn, UserAdminOut

DEMO_COUNTRY = "ES"


@dataclass(frozen=True)
class Scope:
    country_code: str
    scope_type: str
    scope_id: str


@dataclass
class CurrentUser:
    id: str
    name: str
    role: str
    title: str
    scopes: list[Scope] = field(default_factory=list)

    def covers(self, country_code: str, segment: Segment) -> bool:
        return any(
            s.country_code == country_code
            and (
                (s.scope_type == "micro" and s.scope_id == str(segment.id))
                or (s.scope_type == "mega" and s.scope_id == segment.mega_segment_id)
            )
            for s in self.scopes
        )


def demo_user(user_id: str) -> CurrentUser | None:
    user = DEMO_USERS.get(user_id)
    if user is None:
        return None
    return CurrentUser(id=user.id, name=user.name, role=user.role, title=user.title)


def can_submit(user: CurrentUser, country_code: str, segment: Segment) -> bool:
    if user.role != "rep":
        return False
    if get_settings().is_demo:
        return segment.owner_id == user.id and country_code == DEMO_COUNTRY
    return user.covers(country_code, segment)


async def load_user(db: AsyncSession, user_id: str) -> CurrentUser | None:
    user = await db.get(AppUser, user_id)
    if user is None or not user.active:
        return None
    scopes = (await db.execute(select(UserScope).where(UserScope.user_id == user_id))).scalars()
    return CurrentUser(
        id=user.id,
        name=user.name,
        role=user.role,
        title=user.role.capitalize(),
        scopes=[Scope(s.country_code, s.scope_type, s.scope_id) for s in scopes],
    )


async def touch(db: AsyncSession, user_id: str) -> None:
    user = await db.get(AppUser, user_id)
    if user is not None:
        user.last_seen_at = utcnow()
        await db.commit()


async def user_names(db: AsyncSession) -> dict[str, str]:
    names = {u.id: u.name for u in DEMO_USERS.values()}
    names.update({u.id: u.name for u in (await db.execute(select(AppUser))).scalars()})
    return names


async def owners_by_segment(
    db: AsyncSession, country_code: str, segments: list[Segment]
) -> dict[int, list[str]]:
    """Names of the reps who can submit for each segment (demo: the seeded owner)."""
    names = await user_names(db)
    if get_settings().is_demo:
        return {s.id: [names.get(s.owner_id, s.owner_id)] if s.owner_id else [] for s in segments}
    reps = (
        await db.execute(select(AppUser).where(AppUser.role == "rep", AppUser.active.is_(True)))
    ).scalars()
    rep_users = [u for u in reps]
    scopes = (
        (await db.execute(select(UserScope).where(UserScope.country_code == country_code))).scalars().all()
    )
    out: dict[int, list[str]] = {s.id: [] for s in segments}
    for user in rep_users:
        mine = [sc for sc in scopes if sc.user_id == user.id]
        for s in segments:
            if any(
                (sc.scope_type == "micro" and sc.scope_id == str(s.id))
                or (sc.scope_type == "mega" and sc.scope_id == s.mega_segment_id)
                for sc in mine
            ):
                out[s.id].append(user.name)
    return out


async def list_users(db: AsyncSession) -> list[UserAdminOut]:
    users = (await db.execute(select(AppUser).order_by(AppUser.role, AppUser.name))).scalars().all()
    scopes = (await db.execute(select(UserScope))).scalars().all()
    return [
        UserAdminOut(
            email=u.id,
            name=u.name,
            role=u.role,
            active=u.active,
            last_seen_at=u.last_seen_at,
            scopes=[
                ScopeIn(country_code=s.country_code, scope_type=s.scope_type, scope_id=s.scope_id)
                for s in scopes
                if s.user_id == u.id
            ],
        )
        for u in users
    ]


async def upsert_user(
    db: AsyncSession, email: str, name: str, role: str, scopes: list[ScopeIn], active: bool = True
) -> None:
    user_id = email.strip().lower()
    user = await db.get(AppUser, user_id)
    if user is None:
        user = AppUser(id=user_id, name=name, role=role, active=active)
        db.add(user)
    else:
        user.name, user.role, user.active = name, role, active
    await db.flush()
    await db.execute(delete(UserScope).where(UserScope.user_id == user_id))
    seen = set()
    for s in scopes:
        key = (s.country_code.upper(), s.scope_type, s.scope_id)
        if key not in seen:
            seen.add(key)
            db.add(UserScope(user_id=user_id, country_code=key[0], scope_type=key[1], scope_id=key[2]))
    await db.flush()
