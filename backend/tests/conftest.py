import os
import tempfile
from pathlib import Path

_DB = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB}"
os.environ["AUTO_SEED"] = "false"
os.environ["AI_MODE"] = "replay"
os.environ["JEV_API_KEY"] = ""
os.environ["GEMINI_ENABLED"] = "false"
os.environ["CHAT_TURNS_PER_MINUTE"] = "1000"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import async_session, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.seed_service import seed_database  # noqa: E402


@pytest.fixture
async def seeded() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as db:
        await seed_database(db, get_settings().seed_dir)


@pytest.fixture
async def client(seeded: None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
