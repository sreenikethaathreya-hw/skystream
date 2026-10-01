#!/usr/bin/env bash
# Deploy the real-figures app: Cloud Run (europe-west1) + Cloud SQL Postgres, Firebase sign-in.
# The demo stays on its own service (deploy/deploy.sh -> skystream-api, us-central1).
#
# One-time manual step (console only): Firebase console > Authentication > Get started > Sign-in method >
# enable Google, then Settings > Authorized domains > add the Cloud Run host printed at the end.
set -euo pipefail

PROJECT="${PROJECT:-skystream-510015}"
REGION="${REGION:-europe-west1}"
INSTANCE="${INSTANCE:-skystream-pg}"
SERVICE="${SERVICE:-skystream-real}"
DB_NAME="skystream"
DB_USER="skystream"
SA="${SERVICE}@${PROJECT}.iam.gserviceaccount.com"
IMAGE="${IMAGE:-us-central1-docker.pkg.dev/${PROJECT}/skystream/api:latest}"
BOOTSTRAP_ADMINS="${BOOTSTRAP_ADMINS:?set BOOTSTRAP_ADMINS to the comma-separated emails of the first admins}"
FIREBASE_WEB_API_KEY="${FIREBASE_WEB_API_KEY:?set FIREBASE_WEB_API_KEY (firebase apps:sdkconfig WEB <appId>)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> APIs"
gcloud services enable sqladmin.googleapis.com run.googleapis.com secretmanager.googleapis.com \
  aiplatform.googleapis.com identitytoolkit.googleapis.com cloudbuild.googleapis.com --project "$PROJECT"

echo "==> Cloud SQL (${INSTANCE})"
if ! gcloud sql instances describe "$INSTANCE" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud sql instances create "$INSTANCE" --project "$PROJECT" --region "$REGION" --database-version POSTGRES_16 \
    --tier db-f1-micro --edition ENTERPRISE --storage-size 10 --storage-auto-increase --backup-start-time 02:00
fi
CONNECTION="$(gcloud sql instances describe "$INSTANCE" --project "$PROJECT" --format='value(connectionName)')"
gcloud sql databases describe "$DB_NAME" --instance "$INSTANCE" --project "$PROJECT" >/dev/null 2>&1 ||
  gcloud sql databases create "$DB_NAME" --instance "$INSTANCE" --project "$PROJECT"

if ! gcloud secrets describe skystream-db-url --project "$PROJECT" >/dev/null 2>&1; then
  PASSWORD="$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32)"
  gcloud sql users create "$DB_USER" --instance "$INSTANCE" --project "$PROJECT" --password "$PASSWORD" >/dev/null
  printf '%s' "postgresql+asyncpg://${DB_USER}:${PASSWORD}@/${DB_NAME}?host=/cloudsql/${CONNECTION}" |
    gcloud secrets create skystream-db-url --data-file=- --project "$PROJECT" >/dev/null
  unset PASSWORD
fi

echo "==> Service account and IAM"
gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1 ||
  gcloud iam service-accounts create "$SERVICE" --display-name "Skystream real-figures API" --project "$PROJECT"
for role in roles/cloudsql.client roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:${SA}" --role "$role" --condition None >/dev/null
done
SECRETS="DATABASE_URL=skystream-db-url:latest"
gcloud secrets add-iam-policy-binding skystream-db-url --member "serviceAccount:${SA}" \
  --role roles/secretmanager.secretAccessor --project "$PROJECT" >/dev/null
if gcloud secrets describe jev-api-key --project "$PROJECT" >/dev/null 2>&1; then
  gcloud secrets add-iam-policy-binding jev-api-key --member "serviceAccount:${SA}" \
    --role roles/secretmanager.secretAccessor --project "$PROJECT" >/dev/null
  SECRETS="${SECRETS},JEV_API_KEY=jev-api-key:latest"
fi

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "==> Build image"
  gcloud builds submit "$ROOT" --config "$ROOT/deploy/cloudbuild.yaml" --substitutions "_IMAGE=${IMAGE}" --project "$PROJECT"
fi

echo "==> Cloud Run (${SERVICE}, ${REGION})"
# The API enforces Firebase sign-in on every data route; the service is public so the SPA can load.
# DB_USER runs `alembic upgrade head` at container start, so it can also create ADK's chat session tables
# (sessions, events, app_states, user_states, adk_internal_metadata) when the data chat starts.
gcloud run deploy "$SERVICE" --image "$IMAGE" --region "$REGION" --project "$PROJECT" \
  --service-account "$SA" --allow-unauthenticated --add-cloudsql-instances "$CONNECTION" \
  --min-instances 0 --max-instances 3 --memory 1Gi --port 8080 \
  --set-env-vars "^|^DATA_MODE=real|AUTO_SEED=false|NODE_ENV=production|AI_MODE=live|GEMINI_ENABLED=true|GCP_PROJECT=${PROJECT}|GCP_LOCATION=global|GOOGLE_CLOUD_PROJECT=${PROJECT}|GOOGLE_CLOUD_LOCATION=global|GOOGLE_GENAI_USE_ENTERPRISE=True|FIREBASE_PROJECT_ID=${PROJECT}|FIREBASE_AUTH_DOMAIN=${PROJECT}.firebaseapp.com|FIREBASE_WEB_API_KEY=${FIREBASE_WEB_API_KEY}|BOOTSTRAP_ADMIN_EMAILS=${BOOTSTRAP_ADMINS}" \
  --set-secrets "$SECRETS"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format='value(status.url)')"
echo
echo "Deployed: ${URL}"
echo "Firebase console: enable Google sign-in and add '${URL#https://}' to Authentication > Settings > Authorized domains."
