import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models import DemoClock
from app.routers import admin, consensus, demo, entries, meta, segments
from app.services.seed_service import seed_database

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Real mode never seeds: its figures only come from admin uploads.
    if settings.is_demo and settings.auto_seed:
        async with async_session() as db:
            if (await db.execute(select(DemoClock))).scalar_one_or_none() is None:
                logger.info("Seeding demo data from %s", settings.seed_dir)
                await seed_database(db, settings.seed_dir)
    yield


app = FastAPI(
    title="Skystream Demand Ledger API",
    version="0.1.0",
    docs_url=None if settings.is_production else "/docs",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "X-Demo-User", "Authorization"],
)

for module in (meta, segments, entries, demo, consensus, admin):
    app.include_router(module.router)

if (settings.static_dir / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=settings.static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (settings.static_dir / path).resolve()
        if path and candidate.is_file() and settings.static_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(settings.static_dir / "index.html")
