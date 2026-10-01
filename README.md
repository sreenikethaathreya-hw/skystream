# Skystream: Defensible Demand Ledger

A demand-capture tool for **Use Case 2, Market Intelligence and Demand Capture**. A sales rep enters a monthly
demand number for a micro-segment and immediately sees what it does to market share, year-to-go and implied
hectares, with plausibility flags against history. The one-sentence justification becomes a structured,
checkable claim that is resolved when the month's actual sales arrive, and feeds each rep's track record. The
consensus meeting only sees the exceptions.

The app runs in two modes from the same code:

| | Demo (`DATA_MODE=demo`) | Real (`DATA_MODE=real`) |
|---|---|---|
| Figures | Anonymized seed for Spain > Sweet Pepper > Blocky PGH | Whatever admins upload, any country and crop |
| Sign-in | Role switcher (Rep A, Rep B, Consensus lead, Data admin) | Firebase Google sign-in, only registered users |
| Calendar | Simulated clock with **Advance month** | A month closes when its actuals are uploaded |
| Storage | SQLite, reseeded on cold start | Cloud SQL Postgres |
| Jev | Allowed (synthetic text) | Off until an admin enables it after clearance |

- **No forecasting model.** Every number and range comes from the rep.
- **Jev** (TypeSafe decision model) makes classification and verification decisions with probabilities.
  **Gemini** on Vertex AI writes prose and backs up low-confidence Jev answers. Without Jev the app uses recorded
  fixtures, then an offline decider.

## Live

- Demo: https://skystream-510015.web.app
- Real figures: https://skystream-real-842137351485.europe-west1.run.app (needs sign-in; see "First run" below)

## What the admin uploads (real mode)

Upload in the app under **Admin: data**. Every file is validated into a preview (rows read, accepted, rejected
with the reason and row number, warnings) and nothing changes until you **Commit**. Re-uploading a kind for the
same countries replaces it. Upload in this order:

| # | File | Format | Required columns | Notes |
|---|---|---|---|---|
| 1 | Product hierarchy | `.xlsx` (tab `prod hierarchy`) or `.csv` | `f_specie`, `f_megaSegment`, `f_megaSegmentDesc`, `f_microSegment`, `f_microSegmentDesc` | Optional `Cycle`, `Color`, `Ecology Desc`. Everything else is keyed on these IDs. |
| 2 | Market (i-MAPS MAPSHistData export) | as exported | `Country`, `Micro Segment`, `Year`, `Market Planted Area (HA)`, `Market Qty (KS)`, `Market Avg Plant Density`, `Market AvgPrice (ExSeed)` | Optional farmgate price, the six POV note columns, `Modified` (latest wins on duplicates). |
| 3 | Syngenta plan (i-MAPS Syngenta5YrsSales export) | as exported | `Title` (year), `Country`, `Microsegment ID`, `Sales Qty`, `Sales Value` | Missing IDs are recovered from `Microsegment Description`. Optional `FPI Qty`, `Qualitative Comments`. |
| 4 | Competitor shares (i-MAPS CompetitorMktShare export) | as exported | `Forecast Customer Country_D`, `Mega_Segment_Id`, `CompetitorDesc`, `YYYY%` columns | Optional `YYYY` values, `CompetitorTrend`. |
| 5 | Monthly actuals | template (CSV/XLSX) | `country_code`, `micro_segment_id`, `year`, `month`, `sales_qty_ks` | Optional `sales_value_eur` (else plan net price). Committing closes those months and resolves due claims. |
| 6 | Rep assignments | template | `email`, `name`, `role` (admin/lead/rep), `country_code`, `scope_type` (mega/micro), `scope_ids` (`;`-separated) | Also editable in **Admin: users**. |
| 7 | Grower potential (CRM export) | as exported | `Country Name`, `Crop Local`, `Hecatres Info.` | Optional. Rows above the hectare cap (default 500) are capped. |
| 8 | Seasonality | template | `country_code`, `micro_segment_id` or `mega_segment_id`, `month`, `weight` | Optional. Otherwise the plan is split by the last two complete years of actuals, else flat. |

Countries can be ISO codes or names (`Spain`, `SPAIN`, `ES`). **Every kind has a downloadable CSV template** on
the Data screen (or `GET /api/admin/templates/<kind>.csv`). The export-based templates use the exact i-MAPS / CRM
column names, including the optional ones, so the real export can be uploaded unchanged or the template filled
in by hand. Each template's example rows pass its own validator (`backend/tests/test_ingest_templates.py`).

Reps enter, per micro-segment and open month: demand in thousand seeds, a low/high range, an optional net price,
and a justification of up to 600 characters (required when a flag fires). Admins set the planning year,
thresholds, hectare cap, currency and the Jev switch under **Admin: settings**.

## Quick start (local)

```bash
npm install
cd backend && uv sync && uv run alembic upgrade head && uv run python seed.py && cd ..
npm run dev          # demo mode: API on :8000, web on :5173
```

Real mode locally: set `DATA_MODE=real`, `FIREBASE_PROJECT_ID`, `FIREBASE_WEB_API_KEY` and
`BOOTSTRAP_ADMIN_EMAILS=you@company.com` in `backend/.env`, use an empty database, and sign in.

To rebuild the demo seed from the original spreadsheets, put them in `data/raw/` and run `npm run ingest`.

### Optional: live Jev and Gemini

```bash
# backend/.env
JEV_API_KEY=...            # TypeSafe key for https://api.typesafe.ai/v1/systemone
AI_MODE=record             # call Jev live and save fixtures for offline demos
GEMINI_ENABLED=true
GCP_PROJECT=skystream-510015
EXTERNAL_AI_ALLOWED=true   # real mode only, after clearance (also switchable in Admin: settings)
```

## Demo script (about 6 minutes)

1. **Capture** as Rep A, segment 2482 (Autumn late red), September.
2. Type `40000`: share over 100%, hectares above the market, month outlier; submit blocked until justified.
3. Type `14500`, write *"Two Almeria cooperatives are switching from Sur Seeds to Leontes because of
   T. parvispinus tolerance."*, click **Structure with Jev**. The price-carrying warning remains.
4. Submit, then a clean line (2484 at plan). As Rep B submit 2432 for October.
5. As the **Consensus lead**: exceptions only, Jev triage, bulk-approve, **Draft RTB**, export the CSV.
6. **Advance month** (or, as **Data admin**, upload September actuals under **Admin: data**): claims resolve and
   track records update.

## Tests

```bash
cd backend && uv run pytest -v && uv run ruff check .
npm test -w packages/web && npm run lint -w packages/web
npm run test:e2e
```

Backend tests cover the math golden cases, flags, claim checks, AI provider and gate, every upload validator
(fixtures in `tests/fixtures/uploads/`), and real mode end to end (sign-in guards, preview/commit/supersede,
two countries, scopes, actuals closing a month, settings). The math is implemented in Python and TypeScript and
both are held to `tests/fixtures/demand_math_cases.json`, which includes a second country built from uploads.

## Deploy

- `./deploy/deploy.sh`: demo on Cloud Run `skystream-api` (us-central1) + Firebase Hosting.
- `BOOTSTRAP_ADMINS=a@x.com FIREBASE_WEB_API_KEY=... ./deploy/deploy_real.sh`: real mode on Cloud Run
  `skystream-real` (europe-west1) with Cloud SQL Postgres `skystream-pg`, a least-privilege service account,
  the database URL and Jev key from Secret Manager.

### First run of real mode

1. Firebase console > **Authentication** > Get started > Sign-in method > enable **Google**.
2. Authentication > Settings > **Authorized domains**: add `skystream-real-842137351485.europe-west1.run.app`.
3. Sign in with a bootstrap admin email, upload the files above in order, then add reps and leads.
