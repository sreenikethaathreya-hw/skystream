"""Reset the database to the anonymized seed in data/seed. Run `uv run alembic upgrade head` first."""

import asyncio

from app.config import get_settings
from app.database import async_session
from app.services.seed_service import seed_database


async def main() -> None:
    async with async_session() as db:
        await seed_database(db, get_settings().seed_dir)
    print("Seeded demo data")


if __name__ == "__main__":
    asyncio.run(main())
