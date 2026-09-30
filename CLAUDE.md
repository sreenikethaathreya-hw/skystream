# Skystream - Defensible Demand Ledger

Demand-capture tool for Use Case 2 (Market Intelligence and Demand Capture). A sales rep enters a monthly
demand number for a micro-segment and immediately sees market share, year-to-go, implied hectares and
plausibility flags. The justification is structured into a checkable claim that is resolved when actuals
arrive and feeds a per-rep track record. Two modes share one codebase: `DATA_MODE=demo` (anonymized seed,
role switcher, simulated clock) and `DATA_MODE=real` (admin uploads, Firebase sign-in, Cloud SQL).

## Project Layout

| Path | Stack | Purpose |
|------|-------|---------|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy async, Alembic, uv | API server (Cloud Run) |
| `backend/app/ingest/` | pandas | Upload validators (one per file kind), preview reports, commit strategies |
| `packages/web/` | React 19, Vite, TypeScript, TanStack Query, Tailwind v4, Firebase Auth | SPA |
| `scripts/ingest/` | pandas | Builds the anonymized demo seed in `data/seed/` from `data/raw/` |
| `data/seed/` | JSON | Committed, anonymized demo seed. `data/raw/` is gitignored |
| `tests/fixtures/` | JSON / CSV | Golden math cases (Python + TS), recorded AI responses, upload fixtures |
| `tests/e2e/` | Playwright | Demo script and admin upload flow |
| `deploy/` | Shell | `deploy.sh` (demo, us-central1) and `deploy_real.sh` (real, europe-west1 + Cloud SQL) |

## Key Commands

```
npm run dev                              # backend (:8000) + frontend (:5173)
npm run ingest                           # rebuild the demo seed from data/raw/*.xlsx
npm run db:migrate && npm run db:seed    # create schema and load the demo seed
cd backend && uv run pytest -v           # backend tests
cd backend && uv run ruff check .        # backend lint
npm test -w packages/web                 # frontend tests
npm run lint -w packages/web             # frontend type check
npm run test:e2e                         # Playwright (starts both servers)
cd backend && uv run python scripts/gen_golden.py   # regenerate shared math golden cases
```

AI modes (`AI_MODE`): `auto`, `live`, `record`, `replay`. In real mode Jev is only called when the admin
setting `externalAiAllowed` is on (env `EXTERNAL_AI_ALLOWED`); otherwise fixtures, Gemini fallback, offline.

## Non-negotiables

1. **No forecasting model.** Every number and range comes from the rep. The app calculates, checks and records.
2. **Math lives in two mirrored places**: `backend/app/services/demand_math.py` + `flags.py` and
   `packages/web/src/lib/demandMath.ts` + `flags.ts`. Change both and regenerate the golden cases.
3. **Models write no numbers.** Jev returns typed decisions; Gemini writes prose. Both sit behind
   `app/ai/decision_provider.py`, which takes a `DecisionPolicy`; never call a provider client from a router.
4. **Every data route is authenticated** through `app/middleware/auth.get_current_user`. Real mode verifies
   Firebase ID tokens; reps may only submit for segments in their `user_scopes`.
5. **Figures only enter real mode through uploads** (`app/ingest`), which validate into a preview batch before
   an admin commits. Never seed or hand-write figures in real mode.
6. **Postgres identifiers stay under 63 characters**; name long constraints explicitly.
7. **Secrets** (`JEV_API_KEY`, `DATABASE_URL`) live in `.env` locally and Secret Manager in GCP.

## Backend conventions

- Layered: routers (thin HTTP) -> services (logic, DB) -> models (one table per file, re-exported from `app/models/__init__.py`).
- Figures are keyed by `country_code` + micro-segment; the cube and contexts are built per (country, mega-segment).
- Async throughout, SQLAlchemy 2.0 `select()` style, one `commit()` per operation.
- Pydantic schemas in `app/schemas/` serialize to camelCase via `CamelModel`.
- Schema changes go through Alembic (`uv run alembic revision --autogenerate -m "..."`; check with `alembic check`).

## Frontend conventions

- Pages in `src/pages/` (admin screens in `src/pages/admin/`), UI primitives in `src/components/ui/`.
- `SessionProvider` (mode, sign-in, current user) and `ScopeProvider` (country + mega-segment) wrap the app.
- Data fetching through TanStack Query hooks in `src/hooks/queries.ts` and `src/hooks/mutations.ts`.
- The keystroke path must stay client-side: no network call while typing a number.
- `@/` maps to `packages/web/src/`. Strict TypeScript, no `any`.
