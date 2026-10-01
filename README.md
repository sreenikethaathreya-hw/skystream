# Skystream: Defensible Demand Ledger

A demand-capture tool for **Use Case 2, Market Intelligence and Demand Capture**. A sales rep enters a monthly
demand number for a micro-segment and immediately sees what it does to market share, year-to-go and implied
hectares, with plausibility flags against history. The one-sentence justification becomes a structured,
checkable claim that is resolved when the month's actual sales arrive, and feeds each rep's track record. The
consensus meeting only sees the exceptions, and when a number misses, the lead can turn the lesson into a
plain-language rule that is checked on every entry from then on.

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
| 3 | Syngenta sales (i-MAPS Syngenta5YrsSales export) | as exported | `Title` (year), `Country`, `Microsegment ID`, `Sales Qty`, `Sales Value` | Years before the planning year are **actual sales**, the planning year onward is **plan** (SME answer). Missing IDs are recovered from `Microsegment Description`. Optional `FPI Qty`, `Qualitative Comments`, `Avg Net Price` (the preview warns when it differs from value / qty by more than 5%), `Currency` (non-USD values are converted at the budget rate). |
| 4 | Competitor shares (i-MAPS CompetitorMktShare export) | as exported | `Forecast Customer Country_D`, `Mega_Segment_Id`, `CompetitorDesc`, `YYYY%` columns | Optional `YYYY` values, `CompetitorTrend`. |
| 5 | SAC sales and IBP forecast (SAC GPC Sales, query `MDL_LC_FP_Q050`) | as exported, or the template | country, micro-segment ID **or** variety, period, actual/forecast measure (or separate actual and forecast quantity columns), quantity in KS | Optional net sales USD, snapshot date, planner email, currency. Actual rows close their months like the actuals upload; forecast rows become the reps' entries (see "Demand from IBP"). Columns are matched by alias until a real export is available (`backend/app/ingest/sac.py`). |
| 6 | Variety to micro-segment | template | `country_code`, `variety`, `micro_segment_id` | Only needed when the SAC export carries the variety but not the micro-segment. |
| 7 | Monthly actuals | template (CSV/XLSX) | `country_code`, `micro_segment_id`, `year`, `month`, `sales_qty_ks` | Fallback when the SAC export is not used. Optional `sales_value_usd` (else plan net price; `sales_value_eur` is still accepted) and `currency`. Committing closes those months and resolves due claims. |
| 8 | Rep assignments | template | `email`, `name`, `role` (admin/lead/rep), `country_code`, `scope_type` (mega/micro), `scope_ids` (`;`-separated) | Also editable in **Admin: users**. |
| 9 | Budget FX rates | finance `BUD <year>` workbook as delivered, or the template | rate per 1 USD per currency | Optional. Used to show figures in EUR or local currency and to convert local-currency uploads. The finance file is internal: keep it in `data/raw/` (gitignored). |
| 10 | Grower potential (CRM export) | as exported | `Country Name`, `Crop Local`, `Hecatres Info.` | Optional. Rows above the hectare cap (default 500) are capped. |
| 11 | Seasonality | template | `country_code`, `micro_segment_id` or `mega_segment_id`, `month`, `weight` | Optional. Otherwise the plan is split by the last two complete years of actuals, else flat. |

Countries can be ISO codes or names (`Spain`, `SPAIN`, `ES`). **Every kind has a downloadable CSV template** on
the Data screen (or `GET /api/admin/templates/<kind>.csv`). The export-based templates use the exact i-MAPS / CRM
column names, including the optional ones, so the real export can be uploaded unchanged or the template filled
in by hand. Each template's example rows pass its own validator (`backend/tests/test_ingest_templates.py`).

Reps enter, per micro-segment and open month: demand in thousand seeds, a low/high range, an optional net price,
and a justification of up to 600 characters (required when a flag fires). Before typing, the **Baseline** panel
shows share by year (average and high), the month's plan, last year and historical average, and market potential
(planted area, implied hectares, CRM grower potential). Admins set the planning year, thresholds (including the
share-jump limit; agree these with the consensus lead), hectare cap, default display currency, the demand source
and the Jev switch under **Admin: settings**.

## Money: net USD at the budget rate

Every value is stored and computed as **net USD at the Syngenta budget rate** (SME answer). The header's **Show in**
picker displays figures in USD, EUR or the scope country's local currency using the uploaded budget rates; the
conversion happens in the browser, so typing still makes no network call. A net price the rep types is in the
display currency and converted to USD before the math. Flag messages are worded in USD. When feeds later arrive in
local currency, add a `Currency` column and they are converted to USD at the budget rate on upload.

## Demand from IBP

Reps commit demand by variety in IBP, revised monthly, and it reaches SAC (SME answer). With the demand source set
to **IBP** (the real-mode default; the demo starts on **Typed in Capture**):

- Each SAC upload's forecast is rolled up per micro-segment and month, and becomes the rep's entry (`source=ibp`,
  with its snapshot). The owner is the planner named in the file when they are a registered rep, else the only rep
  covering the segment, else **unassigned** (leads see these in the queue). An unchanged number makes no new entry.
- The same flags and lead rules as Capture run on the server. Clean numbers go to consensus as routine; flagged ones
  wait as **needs justification**.
- In **Capture** the month shows "Committed in IBP" with the variety breakdown. The rep adds a range and a
  justification and clicks **Submit justification**; the number box is a what-if only. Typed entries are refused.
- Switching the demo to IBP under **Admin: settings** turns the seeded synthetic snapshot into entries (2432 October
  carries the storyboard's 7,090 KS, so it is flagged).

## Open data assumptions

These are admin settings with defaults until the SMEs confirm them:

| Setting | Default | Alternative |
|---|---|---|
| Plan net price | Sales Value / Sales Qty | the export's `Avg Net Price` |
| Zero hectares in the market file | no market (segment hidden) | data missing (segment shown, share checks off) |
| Days before new actuals resolve claims | 0 (real mode only) | hold N days after month-end; deferred months resolve at a later actuals upload |
| Budget rate for past years | each year's own rate (else the latest) | the current budget rate |
| Score claims against | the plan (direction vs plan, 5% for "no change") | the rep's own number within the tolerance |

## Lead rules

When a claim is contradicted by actuals, the consensus lead (or an admin) clicks **Turn this miss into a rule**
in the Ledger, or writes one under **Lead rules**, e.g. *"Do not accept autumn increases above 20% over last year
for any segment unless the rep names a competitor move."*

- Jev (Gemini fallback, offline decider without either) maps the sentence onto fixed slots only: measure (month
  vs last year / plan / historical average, share level, share jump, range width, price vs plan), above/below,
  this micro-segment or the whole mega-segment, a required justification driver, and warning or hard stop.
- The **limit and months are parsed from the lead's words** (`20%`, `10 pts`, `Oct-Dec`, `autumn`, `Q4`); a rule
  without a number is rejected rather than guessed. Unsupported ideas (process, people, timing) are rejected too.
- Before activating, the lead sees a plain read-back and a **backtest** over every recorded entry in scope: how
  often it would have fired, how many of those claims were later contradicted or confirmed, and whether it would
  have caught the miss it came from.
- Active rules ship with the cube and are evaluated on every keystroke next to the built-in flags
  (`backend/app/services/lead_rules.py` mirrored by `packages/web/src/lib/leadRules.ts`), re-checked on submit, and
  a fired rule that requires a driver the structured claim does not give adds a critical `_unmet` flag.
- Each rule records its author, original sentence, source entry and provider; the Rules page shows how often it
  fired and how those entries resolved, and leads can retire it.

## Ask the data

Every signed-in user has an **Ask the data** button in the header, and pages add **Ask** buttons next to the
thing they are about (a flag, the IBP panel, a justification, an exception card, a ledger entry, a rule, a track
record). The drawer knows which page, segment, month and entry you are on, shows it as an "About: ..." chip you can
clear, and keeps the conversation while it is closed. Answers stream tool progress, then the checked answer.

What it can do, by role:

- **Reps**: a briefing of what needs attention (open months with no entry, IBP numbers waiting for a reason,
  challenged entries with the lead's note, pending and recently resolved claims); why an entry was flagged and the
  limit each check uses; a what-if for a number they type (nothing is saved); market notes, grower potential and
  the variety-to-segment map; a check of their draft justification; their claims, portfolio gap to plan, month
  close recap, own track record against the team average, data freshness and a glossary of terms and how-tos.
  With changes on, they can submit their own number (manual demand source) or justify an IBP number.
- **Consensus leads**: everything above for all segments, plus coverage for a month ("is October ready to
  close?"), a walkthrough of any entry with Jev's triage probabilities, rep accuracy by month, rankings (entry vs
  plan, last year or IBP, range width, gap to plan), claim themes, an entry's full history including changes made
  through the chat, an RTB draft and the supply CSV. With changes on, they can approve, discuss or challenge an
  entry, bulk-approve routine entries, leave a note for the rep, and compile, activate or retire a lead rule.
- **Admins**: upload status, who covers which segment, settings and the thresholds behind each flag, data quality.
  Uploads, users and settings themselves stay on the admin pages.

How it is kept honest:

- A Google ADK agent on Gemini (Vertex) answers through tools in `backend/app/ai/data_agent/` (`tools.py`,
  `rep_tools.py`, `lead_tools.py`, `admin_tools.py` read; `actions.py` writes). The server writes the caller's
  scope and page into ADK state on each turn; tools and `ScopeGuardPlugin` refuse segments outside it, and lead and
  admin tools are role-gated.
- **No invented numbers.** `NumberGuardPlugin` checks every number in the answer against the tool results and
  the question, and replaces any it cannot match with "(see table)". The tool tables are shown under each answer.
- **The model never authors a number or a claim.** `WriteGuardPlugin` lets a number into a what-if or a write only
  if the user typed it in that message, and a justification, note or rule sentence only if it quotes the user. Writes
  also need the right role, the `chatWritesAllowed` setting (Admin: settings; always on in demo) and are limited to
  one per message. Every write goes through the same service the UI uses and is logged in `chat_actions`; the UI
  shows a receipt and refreshes the affected pages.
- **No forecasting.** A question asking for a prediction is classified first (Jev when allowed, otherwise a
  keyword decider) and gets a fixed refusal.
- Without Gemini, a template fallback answers the read intents from one tool each (using the page context for
  "this entry"), and change requests point to the page that makes them, so the demo works offline.
- Conversations are stored per user in ADK's `DatabaseSessionService` on the app database; demo reset clears them.
  Each user is limited to `CHAT_TURNS_PER_MINUTE` questions per minute.
- Entry notes (`entry_notes`) carry the lead's question and the rep's answer on an entry; they show on Capture,
  Ledger and Consensus and in the rep's briefing.

Local debugging with ADK's own tools (needs Gemini and a seeded database):

```bash
cd backend
GEMINI_ENABLED=true GCP_PROJECT=skystream-510015 uv run adk web app/ai
RUN_LIVE_EVAL=1 GEMINI_ENABLED=true GCP_PROJECT=skystream-510015 uv run pytest tests/eval
JEV_API_KEY=... AI_MODE=record uv run python scripts/record_chat_intents.py   # record chat-intent fixtures
```

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
7. Storyboard check: as Rep B, 2432 October, type `7090`. Share moves 20.2% to 35.0%, year-to-go turns green and
   the share-jump flag reads *"This entry is 193% above the historical October average ... and lifts share from
   20.2% to 35.0% (+14.8 pts)."*
8. As the lead, Ledger > **Missed claims only** > **Turn this miss into a rule**; check, read the backtest, activate.
   Back as Rep A the rule fires as you type.
9. **Ask the data**: as Rep A ask *"What is the share for 2482 in October?"*; the answer quotes the baseline
   figures and shows the table. Ask it to forecast October and it declines. Click **Why?** on a flag after
   submitting and it explains the check and its limit.
10. With Gemini on, as Rep A ask *"Please submit 4000 KS for 2482 in October, range 3800 to 4200, because ..."*:
    a receipt appears and Capture updates. As the lead ask *"Is October ready to close?"*, then *"Challenge
    Rep B's October entry for 2432: which distributor?"*; Rep B sees the note in Capture and in their briefing.

## Tests

```bash
cd backend && uv run pytest -v && uv run ruff check .
npm test -w packages/web && npm run lint -w packages/web
npm run test:e2e
```

Backend tests cover the math golden cases, flags, claim checks, AI provider and gate, every upload validator
(fixtures in `tests/fixtures/uploads/`), and real mode end to end (sign-in guards, preview/commit/supersede,
two countries, scopes, actuals closing a month, settings) and lead rules (parsing, read-back, backtest, lifecycle,
unmet driver), and the data chat (tools, scope and number guards, sessions, a scripted fake model for the
agent loop, plus an opt-in live ADK evalset in `backend/tests/eval`). The math, flag wording and lead-rule evaluation are implemented in Python and TypeScript and both
are held to `tests/fixtures/demand_math_cases.json` and `tests/fixtures/lead_rule_cases.json`.

## Deploy

- `./deploy/deploy.sh`: demo on Cloud Run `skystream-api` (us-central1) + Firebase Hosting.
- `BOOTSTRAP_ADMINS=a@x.com FIREBASE_WEB_API_KEY=... ./deploy/deploy_real.sh`: real mode on Cloud Run
  `skystream-real` (europe-west1) with Cloud SQL Postgres `skystream-pg`, a least-privilege service account,
  the database URL and Jev key from Secret Manager.

### First run of real mode

1. Firebase console > **Authentication** > Get started > Sign-in method > enable **Google**.
2. Authentication > Settings > **Authorized domains**: add `skystream-real-842137351485.europe-west1.run.app`.
3. Sign in with a bootstrap admin email, upload the files above in order, then add reps and leads.
