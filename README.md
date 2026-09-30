# Skystream: Defensible Demand Ledger

Demo app for **Use Case 2, Market Intelligence and Demand Capture**. A sales rep enters a monthly demand
number for one locked crop and geography (**Spain > Sweet Pepper > Blocky PGH**) and immediately sees what it
does to market share, year-to-go and implied hectares, with plausibility flags against history. The
one-sentence justification becomes a structured, checkable claim that is resolved against later data and
feeds each rep's track record. The consensus meeting only sees the exceptions.

- **No forecasting model.** Every number and range comes from the rep.
- **Jev** (TypeSafe decision model) makes every classification and verification decision with probabilities.
  **Gemini** on Vertex AI only writes prose (claim summary, reasons-to-believe) and backs up low-confidence Jev
  answers. Without keys the app replays recorded Jev fixtures, then falls back to an offline decider.
- **Synthetic data.** Syngenta figures are scaled and noised at ingest; rep names are pseudonymized.

## Quick start

```bash
npm install
cd backend && uv sync && uv run alembic upgrade head && uv run python seed.py && cd ..
npm run dev          # API on :8000, web on :5173
```

Open http://localhost:5173. Switch between **Rep A**, **Rep B** and the **Consensus lead** from the header.

To rebuild the seed from the original spreadsheets, put them in `data/raw/` and run `npm run ingest`.

### Optional: live Jev and Gemini

```bash
# backend/.env
JEV_API_KEY=...            # TypeSafe key for https://api.typesafe.ai/v1/systemone
AI_MODE=record             # call Jev live and save fixtures for offline demos
GEMINI_ENABLED=true
GCP_PROJECT=skystream-510015
```

Gemini uses Application Default Credentials (`gcloud auth application-default login`).

## Demo script (about 6 minutes)

1. **Capture** as Rep A, segment 2482 (Autumn late red), September. The tiles show share, year-to-go and
   implied hectares for the plan number.
2. Type `40000`: share goes over 100%, implied hectares exceed the market, the number is an outlier, and
   submit is blocked until there is a justification.
3. Type `14500` and write *"Two Almeria cooperatives are switching from Sur Seeds to Leontes because of
   T. parvispinus tolerance."* Click **Structure with Jev** to see the typed decisions with probabilities.
   The price-carrying warning remains: volume is below last year and price is holding revenue up.
4. Submit, then submit a clean line (e.g. 2484 at plan). Switch to Rep B and submit 2432 for October.
5. Switch to the **Consensus lead**. Only the exceptions are on the agenda, each with Jev's triage suggestion.
   Bulk-approve the routine line, approve the rest, **Draft RTB** for 2482, export the supply CSV.
6. **Advance month**. September claims resolve against synthetic actuals (numeric check plus Jev's yes/no
   verdict), and the **Track record** page updates.
7. **Data quality** shows what the ingest found and fixed in the spreadsheets.

## Tests

```bash
cd backend && uv run pytest -v && uv run ruff check .
npm test -w packages/web && npm run lint -w packages/web
npm run test:e2e
```

The math is implemented twice (Python for validation on submit, TypeScript for zero-latency recalculation) and
both are held to the same golden cases in `tests/fixtures/demand_math_cases.json`.

## Deploy

Live demo: https://skystream-510015.web.app (Firebase Hosting, proxies `/api` to Cloud Run). The Cloud Run URL
https://skystream-api-842137351485.us-central1.run.app serves the same app directly. Project `skystream-510015`.

`./deploy/deploy.sh` builds one image with Cloud Build (the SPA is compiled in and served by FastAPI), deploys it
to Cloud Run (one instance, SQLite reseeded on cold start), then publishes the SPA to Firebase Hosting, which
proxies `/api` to Cloud Run. The Cloud Run URL is a complete app on its own; the Firebase step needs
`firebase login` with an account that can access the project.

- Gemini runs on Vertex AI's `global` endpoint (`gemini-3.8-flash` is not served in `us-central1`) as the
  `skystream-api` service account with `roles/aiplatform.user`.
- Gemini never sits on the entry path: claim summaries are rewritten in a background task after submit.
- Live Jev is on: the key is in Secret Manager as `jev-api-key`, mounted as `JEV_API_KEY`, with `AI_MODE=live`.
  A fresh justification takes about 0.3 s (one fan-out call), about 1.3 s when a low-confidence field falls
  back to Gemini (5 s cap), and repeats are cached.
