# Skystream - Defensible Demand Ledger

Demo app for Use Case 2 (Market Intelligence and Demand Capture). A sales rep enters a monthly demand
number for one locked crop and geography (Spain > Sweet Pepper > Blocky PGH) and immediately sees
market share, year-to-go, implied hectares and plausibility flags. The justification is structured
into a checkable claim that is resolved against later data and feeds a per-rep track record.

## Project Layout

| Path | Stack | Purpose |
|------|-------|---------|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy async, Alembic, uv | API server (Cloud Run) |
| `packages/web/` | React 19, Vite, TypeScript, TanStack Query, Tailwind v4 | SPA (Firebase Hosting) |
| `scripts/ingest/` | pandas | Turns the raw spreadsheets in `data/raw/` into anonymized JSON in `data/seed/` |
| `data/seed/` | JSON | Committed, anonymized seed data. `data/raw/` is gitignored |
| `tests/fixtures/` | JSON | Shared golden cases (Python + TS) and recorded AI responses |
| `tests/e2e/` | Playwright | Demo-script happy path |
| `deploy/` | Shell | GCP deploy (Cloud Run + Firebase Hosting) |

## Key Commands

```
npm run dev                              # backend (:8000) + frontend (:5173)
npm run ingest                           # rebuild data/seed from data/raw/*.xlsx
npm run db:migrate && npm run db:seed    # create schema and load seed data
cd backend && uv run pytest -v           # backend tests
cd backend && uv run ruff check .        # backend lint
npm test -w packages/web                 # frontend tests
npm run lint -w packages/web             # frontend type check
npm run test:e2e                         # Playwright (starts both servers)
cd backend && uv run python scripts/gen_golden.py   # regenerate shared math golden cases
./deploy/deploy.sh                       # Cloud Run + Firebase Hosting (needs billing and CLI auth)
```

AI modes (`AI_MODE`): `auto` (Jev if `JEV_API_KEY` is set, else replay), `live`, `record` (live + save
fixtures to `tests/fixtures/ai/`), `replay` (recorded fixtures, then the offline decider). Gemini is used only
when `GEMINI_ENABLED=true` and `GCP_PROJECT` is set.

## Non-negotiables

1. **No forecasting model.** Every number and range comes from the rep. The app calculates, checks and records.
2. **Math lives in two mirrored places**: `backend/app/services/demand_math.py` + `flags.py` and
   `packages/web/src/lib/demandMath.ts` + `flags.ts`. Any change must update both and
   `tests/fixtures/demand_math_cases.json` (regenerate with `uv run python scripts/gen_golden.py`).
3. **Models write no numbers.** Jev returns typed decisions (Choice / Score / Noul); Gemini writes prose
   only. Both sit behind `app/ai/decision_provider.py`; never call a provider client from a router.
4. **Synthetic data only.** Syngenta figures are scaled and noised at ingest and rep names are
   pseudonymized. Never commit `data/raw/` or anything derived from it without anonymization.
5. **Secrets** (`JEV_API_KEY`) live in `.env` locally and Secret Manager in GCP. Never commit them.

## Backend conventions

- Layered: routers (thin HTTP) -> services (logic, DB) -> models (one table per file, re-exported from `app/models/__init__.py`).
- Async throughout, SQLAlchemy 2.0 `select()` style, one `commit()` per operation.
- Pydantic schemas in `app/schemas/` serialize to camelCase via `CamelModel`.
- Schema changes go through Alembic (`uv run alembic revision --autogenerate -m "..."`).

## Frontend conventions

- Pages in `src/pages/`, UI primitives in `src/components/ui/`, feature components in `src/components/<feature>/`.
- Data fetching through TanStack Query hooks in `src/hooks/queries.ts` and `src/hooks/mutations.ts`.
- The keystroke path must stay client-side: no network call while typing a number.
- `@/` maps to `packages/web/src/`. Strict TypeScript, no `any`.
