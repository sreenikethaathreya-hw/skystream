import asyncio
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)
_app = None


class TokenError(Exception):
    pass


def _firebase_app():
    global _app
    if _app is None:
        import firebase_admin

        project_id = get_settings().firebase_project_id
        if not project_id:
            raise TokenError("FIREBASE_PROJECT_ID is not configured")
        _app = firebase_admin.initialize_app(options={"projectId": project_id}, name="skystream")
    return _app


def _verify(token: str) -> dict:
    from firebase_admin import auth

    try:
        return auth.verify_id_token(token, app=_firebase_app(), check_revoked=False)
    except TokenError:
        raise
    except Exception as exc:  # firebase_admin raises several token error types
        raise TokenError(str(exc)) from exc


async def verify_id_token(token: str) -> dict:
    """Verify a Firebase ID token (signature, expiry, audience) and return its claims."""
    return await asyncio.to_thread(_verify, token)
