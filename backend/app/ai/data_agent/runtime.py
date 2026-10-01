"""Process-wide ADK runner and session service, created once at startup."""

import logging
from dataclasses import dataclass

from google.adk import Runner
from google.adk.models import BaseLlm
from google.adk.sessions import DatabaseSessionService

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class DataAgentRuntime:
    runner: Runner
    sessions: DatabaseSessionService
    app_name: str


_runtime: DataAgentRuntime | None = None


async def init_data_agent(model: BaseLlm | None = None) -> DataAgentRuntime:
    """Builds the runner on the app's own engine and creates ADK's session tables if they are missing."""
    global _runtime
    from app.ai.data_agent.agent import app, build_app
    from app.database import engine

    sessions = DatabaseSessionService(db_engine=engine)
    await sessions.prepare_tables()
    adk_app = build_app(model) if model is not None else app
    _runtime = DataAgentRuntime(
        runner=Runner(app=adk_app, session_service=sessions), sessions=sessions, app_name=adk_app.name
    )
    logger.info("Data chat ready (app %s, model %s)", adk_app.name, get_settings().gemini_model)
    return _runtime


def get_runtime() -> DataAgentRuntime | None:
    return _runtime
