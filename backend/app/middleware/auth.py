from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware import firebase_verifier
from app.services.user_service import CurrentUser, demo_user, load_user, upsert_user


async def get_current_user(
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    settings = get_settings()
    if settings.is_demo:
        user = demo_user(x_demo_user or "rep-a")
        if user is None:
            raise HTTPException(status_code=401, detail="Unknown demo user")
        return user

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in required")
    try:
        claims = await firebase_verifier.verify_id_token(authorization.split(" ", 1)[1])
    except firebase_verifier.TokenError as exc:
        raise HTTPException(
            status_code=401, detail="Your session is invalid or expired; sign in again"
        ) from exc
    email = (claims.get("email") or "").lower()
    if not email or not claims.get("email_verified", False):
        raise HTTPException(status_code=403, detail="A verified email is required")

    user = await load_user(db, email)
    if user is None and email in settings.bootstrap_admins:
        await upsert_user(db, email, claims.get("name") or email, "admin", [])
        await db.commit()
        user = await load_user(db, email)
    if user is None:
        raise HTTPException(status_code=403, detail="Your account is not registered; ask an admin to add you")
    return user


def require_role(user: CurrentUser, *roles: str) -> None:
    if user.role not in roles:
        raise HTTPException(status_code=403, detail=f"This needs the {' or '.join(roles)} role")
