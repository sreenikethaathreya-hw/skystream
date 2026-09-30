#!/usr/bin/env bash
# Deploy the demo: API to Cloud Run, SPA to Firebase Hosting (which proxies /api to Cloud Run).
# Prerequisites: billing enabled on the project, gcloud and firebase CLIs signed in with access to it.
# Optional: put the Jev key in Secret Manager first:
#   printf '%s' "$JEV_API_KEY" | gcloud secrets create jev-api-key --data-file=- --project "$PROJECT"
set -euo pipefail

PROJECT="${PROJECT:-skystream-510015}"
REGION="${REGION:-us-central1}"
SERVICE="skystream-api"
SA="skystream-api@${PROJECT}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/skystream/api:latest"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Enabling APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com aiplatform.googleapis.com firebasehosting.googleapis.com --project "$PROJECT"

echo "==> Artifact Registry and service account"
gcloud artifacts repositories describe skystream --location "$REGION" --project "$PROJECT" >/dev/null 2>&1 ||
  gcloud artifacts repositories create skystream --repository-format docker --location "$REGION" --project "$PROJECT"
gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1 ||
  gcloud iam service-accounts create skystream-api --display-name "Skystream API" --project "$PROJECT"
gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:${SA}" \
  --role roles/aiplatform.user --condition None >/dev/null

SECRET_FLAGS=()
AI_MODE="replay"
if gcloud secrets describe jev-api-key --project "$PROJECT" >/dev/null 2>&1; then
  gcloud secrets add-iam-policy-binding jev-api-key --member "serviceAccount:${SA}" \
    --role roles/secretmanager.secretAccessor --project "$PROJECT" >/dev/null
  SECRET_FLAGS=(--set-secrets "JEV_API_KEY=jev-api-key:latest")
  AI_MODE="live"
fi

echo "==> Building image"
gcloud builds submit "$ROOT" --config "$ROOT/deploy/cloudbuild.yaml" \
  --substitutions "_IMAGE=${IMAGE}" --project "$PROJECT"

echo "==> Deploying Cloud Run service (AI_MODE=${AI_MODE})"
gcloud run deploy "$SERVICE" --image "$IMAGE" --region "$REGION" --project "$PROJECT" \
  --service-account "$SA" --allow-unauthenticated --max-instances 1 --min-instances 0 \
  --memory 1Gi --port 8080 \
  --set-env-vars "AI_MODE=${AI_MODE},GEMINI_ENABLED=true,GCP_PROJECT=${PROJECT},GCP_LOCATION=global" \
  "${SECRET_FLAGS[@]}"

echo "==> Building and deploying the SPA to Firebase Hosting"
(cd "$ROOT" && npm run build:web)
firebase projects:addfirebase "$PROJECT" >/dev/null 2>&1 || true
(cd "$ROOT" && firebase deploy --only hosting --project "$PROJECT")
