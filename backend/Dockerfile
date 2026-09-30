# Build from the repo root so the SPA, seed data and recorded AI fixtures are included:
#   docker build -f backend/Dockerfile .
FROM node:22-slim AS web
WORKDIR /repo
COPY package.json package-lock.json ./
COPY packages/web/package.json packages/web/
COPY tests/e2e/package.json tests/e2e/
RUN npm ci --workspace packages/web
COPY packages/web packages/web
COPY tests/fixtures tests/fixtures
RUN npm run build --workspace packages/web

FROM python:3.12-slim
WORKDIR /app/backend
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
COPY data/seed/ /app/data/seed/
COPY tests/fixtures/ /app/tests/fixtures/
COPY --from=web /repo/packages/web/dist /app/packages/web/dist
RUN uv sync --frozen --no-dev

ENV PORT=8080 \
    NODE_ENV=production \
    DATABASE_URL=sqlite+aiosqlite:////tmp/skystream.db \
    SEED_DIR=/app/data/seed \
    FIXTURES_DIR=/app/tests/fixtures/ai \
    STATIC_DIR=/app/packages/web/dist \
    AUTO_SEED=true
EXPOSE 8080

# SQLite in /tmp is per-instance and resets on cold start, which is what a demo wants.
# Run with --max-instances=1 so every request sees the same ledger; set DATABASE_URL to Cloud SQL for persistence.
CMD ["sh", "-c", "/app/backend/.venv/bin/alembic upgrade head && /app/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
