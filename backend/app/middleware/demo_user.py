from fastapi import Header, HTTPException

from app.constants.demo import DEMO_USERS, DemoUser


async def get_current_user(x_demo_user: str = Header(default="rep-a")) -> DemoUser:
    """Demo role switcher. Replace with Firebase Auth before any real data is used."""
    user = DEMO_USERS.get(x_demo_user)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown demo user")
    return user


def require_role(user: DemoUser, role: str) -> None:
    if user.role != role:
        raise HTTPException(status_code=403, detail=f"Only a {role} can do this")
