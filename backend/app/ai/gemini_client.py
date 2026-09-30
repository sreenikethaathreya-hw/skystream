import asyncio
import json
import logging

from app.config import Settings

logger = logging.getLogger(__name__)


class GeminiError(RuntimeError):
    pass


class GeminiClient:
    """Gemini on Vertex AI. Used only for prose and for low-confidence field extraction."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    @property
    def available(self) -> bool:
        return self._settings.gemini_enabled and bool(self._settings.gcp_project)

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(
                vertexai=True,
                project=self._settings.gcp_project,
                location=self._settings.gcp_location,
            )
        return self._client

    async def write(self, prompt: str, max_words: int = 120) -> str:
        if not self.available:
            raise GeminiError("Gemini is not enabled")
        from google.genai import types

        try:
            response = await self._get_client().aio.models.generate_content(
                model=self._settings.gemini_model,
                contents=f"{prompt}\n\nKeep it under {max_words} words. Plain text, no markdown.",
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                ),
            )
        except Exception as exc:  # the SDK raises several transport-specific types
            raise GeminiError(str(exc)) from exc
        return (response.text or "").strip()

    async def extract(self, prompt: str, schema: dict, timeout_seconds: float) -> dict:
        if not self.available:
            raise GeminiError("Gemini is not enabled")
        from google.genai import types

        try:
            response = await asyncio.wait_for(
                self._get_client().aio.models.generate_content(
                    model=self._settings.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                        response_schema=schema,
                        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                    ),
                ),
                timeout=timeout_seconds,
            )
            return json.loads(response.text or "{}")
        except TimeoutError as exc:
            raise GeminiError(f"timed out after {timeout_seconds}s") from exc
        except Exception as exc:
            raise GeminiError(str(exc)) from exc
