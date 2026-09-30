from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "demo" serves the anonymized seed with a simulated clock and a role switcher.
    # "real" serves uploaded figures, Firebase sign-in and a calendar driven by uploaded actuals.
    data_mode: Literal["demo", "real"] = "demo"

    database_url: str = "sqlite+aiosqlite:///./skystream.db"
    seed_dir: Path = REPO_ROOT / "data" / "seed"
    fixtures_dir: Path = REPO_ROOT / "tests" / "fixtures" / "ai"
    cors_origin: str = "http://localhost:5173"
    auto_seed: bool = True
    node_env: str = "development"

    # Planning year in real mode; defaults to the calendar year.
    current_year: int | None = None

    # "auto" uses Jev when a key is present, otherwise replays recorded fixtures.
    ai_mode: Literal["auto", "live", "record", "replay"] = "auto"
    jev_api_key: str | None = None
    jev_base_url: str = "https://api.typesafe.ai/v1"
    jev_model: str = "jev-1.13.0"
    jev_timeout_seconds: float = 5.0
    jev_confidence_threshold: float = 0.8
    # Score confidence is the probability of the winning level on a 4-level rubric, so it runs lower than Choice.
    jev_score_confidence_threshold: float = 0.4
    # Real justification text only leaves GCP for Jev's hosted API once Syngenta has cleared it.
    external_ai_allowed: bool = False

    gemini_enabled: bool = False
    gcp_project: str | None = None
    # Newer Gemini models are served from the global Vertex endpoint, not every region.
    gcp_location: str = "global"
    static_dir: Path = REPO_ROOT / "packages" / "web" / "dist"
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_timeout_seconds: float = 5.0

    firebase_project_id: str | None = None
    firebase_web_api_key: str | None = None
    firebase_auth_domain: str | None = None
    # Comma-separated emails that become admins on first sign-in (bootstraps an empty real deployment).
    bootstrap_admin_emails: str = ""

    grower_ha_cap: float = 500.0
    currency: str = "EUR"

    @property
    def is_production(self) -> bool:
        return self.node_env == "production"

    @property
    def is_demo(self) -> bool:
        return self.data_mode == "demo"

    @property
    def bootstrap_admins(self) -> set[str]:
        return {e.strip().lower() for e in self.bootstrap_admin_emails.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
