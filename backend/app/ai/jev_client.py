import httpx

from app.config import Settings


class JevError(RuntimeError):
    pass


class JevClient:
    """Thin client for TypeSafe's Jev `systemone` endpoint (typed decisions, no text)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def available(self) -> bool:
        return bool(self._settings.jev_api_key)

    async def ask(self, state: str, questions: dict[str, dict]) -> dict:
        if not self.available:
            raise JevError("JEV_API_KEY is not configured")
        body = {"model": self._settings.jev_model, "state": state, "questions": questions}
        headers = {"Authorization": f"Bearer {self._settings.jev_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self._settings.jev_timeout_seconds) as client:
                response = await client.post(
                    f"{self._settings.jev_base_url}/systemone", json=body, headers=headers
                )
        except httpx.HTTPError as exc:
            raise JevError(f"Jev request failed: {exc}") from exc
        if response.status_code != 200:
            raise JevError(f"Jev returned {response.status_code}: {response.text[:200]}")
        payload = response.json()
        return {"model": payload.get("model"), "answers": payload.get("answers", {})}
