from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./skystream.db"
    seed_dir: Path = REPO_ROOT / "data" / "seed"
    fixtures_dir: Path = REPO_ROOT / "tests" / "fixtures" / "ai"
    cors_origin: str = "http://localhost:5173"
    auto_seed: bool = True
    node_env: str = "development"

    # "auto" uses Jev when a key is present, otherwise replays recorded fixtures.
    ai_mode: Literal["auto", "live", "record", "replay"] = "auto"
    jev_api_key: str | None = None
    jev_base_url: str = "https://api.typesafe.ai/v1"
    jev_model: str = "jev-1.13.0"
    jev_timeout_seconds: float = 5.0
    jev_confidence_threshold: float = 0.8
    # Score confidence is the probability of the winning level on a 4-level rubric, so it runs lower than Choice.
    jev_score_confidence_threshold: float = 0.4

    gemini_enabled: bool = False
    gcp_project: str | None = None
    # Newer Gemini models are served from the global Vertex endpoint, not every region.
    gcp_location: str = "global"
    static_dir: Path = REPO_ROOT / "packages" / "web" / "dist"
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_timeout_seconds: float = 5.0

    @property
    def is_production(self) -> bool:
        return self.node_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
