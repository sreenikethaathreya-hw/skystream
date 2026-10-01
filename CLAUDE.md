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
| `backend/app/ai/data_agent/` | Google ADK, Gemini | "Ask the data" assistant: read tools per role, guarded write tools, guard plugins, ADK sessions |
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
cd backend && RUN_LIVE_EVAL=1 GEMINI_ENABLED=true GCP_PROJECT=... uv run pytest tests/eval   # live ADK evalset
```

AI modes (`AI_MODE`): `auto`, `live`, `record`, `replay`. In real mode Jev is only called when the admin
setting `externalAiAllowed` is on (env `EXTERNAL_AI_ALLOWED`); otherwise fixtures, Gemini fallback, offline.

## Non-negotiables

1. **No forecasting model.** Every number and range comes from the rep. The app calculates, checks and records.
 Reps commit demand by variety in IBP; `app/services/ibp_service.py` imports that number (SAC upload) as the rep's
 entry (`source="ibp"`) and the rep only justifies it in Skystream. Never generate or adjust an IBP number.
2. **Math lives in two mirrored places**: `backend/app/services/demand_math.py` + `flags.py` + `lead_rules.py` and
 `packages/web/src/lib/demandMath.ts` + `flags.ts` + `leadRules.ts`. Change both and regenerate the golden cases
 (flag messages are compared word for word).
8. **Lead rules** compile a lead's sentence into fixed slots (`app/services/rule_service.py`). Models only pick
 slots; the limit and months are parsed from the text, and a rule without a number is rejected.
3. **Models write no numbers.** Jev returns typed decisions; Gemini writes prose. Both sit behind
   `app/ai/decision_provider.py`, which takes a `DecisionPolicy`; never call a provider client from a router.
4. **Every data route is authenticated** through `app/middleware/auth.get_current_user`. Real mode verifies
   Firebase ID tokens; reps may only submit for segments in their `user_scopes`.
5. **Figures only enter real mode through uploads** (`app/ingest`), which validate into a preview batch before
   an admin commits. Never seed or hand-write figures in real mode. Money is stored as **net USD at the budget
   rate** (`*_usd` columns); local-currency uploads are converted on upload, and other currencies are display-only,
   converted in the browser from the cube's `fx` rates (`src/lib/money.ts`). The finance rate file is internal and
   stays in `data/raw/`.
6. **Postgres identifiers stay under 63 characters**; name long constraints explicitly.
9. **Ask the data** (`app/ai/data_agent/`) is a Google ADK agent on Gemini, reached only through
 `DecisionProvider.answer_data_question`. Read tools (`tools.py`, `rep_tools.py`, `lead_tools.py`,
 `admin_tools.py`) never write; write tools live only in `actions.py`, call the same services as the UI, and pass
 `WriteGuardPlugin`: role allowlists in `policy.py`, the `chatWritesAllowed` setting, one write per turn, numbers
 (`USER_NUMBER_ARGS`) the user typed this turn and justification/note/rule text quoted from the user. All tools
 enforce the per-turn `temp:policy` the server writes into ADK state (scope, role, visible segments, writes,
 demand source) and read the page from `temp:page_context`; `ScopeGuardPlugin` re-checks arguments and
 role-gated tools. Every number in an answer must appear in a tool result or the question, enforced by
 `NumberGuardPlugin`; it never forecasts. `AuditPlugin` records each write attempt in `chat_actions`. ADK owns
 its session tables (`sessions`, `events`, `app_states`, `user_states`, `adk_internal_metadata`), which
 `alembic/env.py` excludes; do not model them in `app/models`.
7. **Secrets** (`JEV_API_KEY`, `DATABASE_URL`) live in `.env` locally and Secret Manager in GCP.

## Backend conventions

- Layered: routers (thin HTTP) -> services (logic, DB) -> models (one table per file, re-exported from `app/models/__init__.py`).
- Figures are keyed by `country_code` + micro-segment; the cube and contexts are built per (country, mega-segment).
- Syngenta5YrsSales rows before the planning year are actual sales, the planning year onward is plan
  (`cube_builder.plan_row_basis`). SME assumptions awaiting confirmation are `AppSettings` fields, not constants.
- Async throughout, SQLAlchemy 2.0 `select()` style, one `commit()` per operation.
- Pydantic schemas in `app/schemas/` serialize to camelCase via `CamelModel`.
- Schema changes go through Alembic (`uv run alembic revision --autogenerate -m "..."`; check with `alembic check`).

## Frontend conventions

- Pages in `src/pages/` (admin screens in `src/pages/admin/`), UI primitives in `src/components/ui/`.
- `SessionProvider` (mode, sign-in, current user) and `ScopeProvider` (country + mega-segment) wrap the app.
- `ChatProvider` (`src/hooks/useChat.tsx`) owns the assistant drawer: pages call `usePageContext` (ids only,
  never figures) and place `AskButton`s; assistant changes invalidate queries via `src/lib/chatActions.ts`.
- Capture widgets: built-ins live in `src/components/widgets/registry.tsx` and start hidden; each user's choice is
  saved in `user_widget_prefs`. Tables from `PINNABLE_TOOLS` (`policy.py`) can be pinned from the chat into
  `user_widgets`, which store only the tool and its arguments; `widget_service.run_widget` re-runs the tool under
  the viewer's current policy, never the model.
- Data fetching through TanStack Query hooks in `src/hooks/queries.ts` and `src/hooks/mutations.ts`.
- The keystroke path must stay client-side: no network call while typing a number.
- `@/` maps to `packages/web/src/`. Strict TypeScript, no `any`.
