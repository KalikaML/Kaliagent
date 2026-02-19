#!/bin/bash
set -euo pipefail

# ===========================================================
# Cloud Run Deployment Script (Django + Neon PostgreSQL)
# Version: v3 - Updated for Current Project Version
# ===========================================================

# CONFIG VARIABLES
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
IMAGE_REPO="${IMAGE_REPO:-command-center-repo}"
IMAGE_NAME="${IMAGE_NAME:-command-center}"
TAG="${TAG:-v1}"
SERVICE_NAME="${SERVICE_NAME:-command-center-uat}"
SA_NAME="${SA_NAME:-$SERVICE_NAME-sa}"

if [ -z "$PROJECT_ID" ]; then
  echo "Please set your gcloud project first:"
  echo "  gcloud config set project <PROJECT_ID>"
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${IMAGE_REPO}/${IMAGE_NAME}:${TAG}"

echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Image: $IMAGE"
echo ""

# 1. Enable required APIs
echo "Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  --project "$PROJECT_ID"

# 2. Create Artifact Registry (if not exists)
if ! gcloud artifacts repositories describe "$IMAGE_REPO" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "Creating Artifact Registry..."
  gcloud artifacts repositories create "$IMAGE_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --project "$PROJECT_ID"
else
  echo "Artifact Registry already exists."
fi

# 3. Build & push image to Artifact Registry
echo "Building and pushing Docker image..."
gcloud builds submit --tag "$IMAGE" .

# 4. Create or reuse service account
echo "Ensuring service account exists..."
gcloud iam service-accounts create "$SA_NAME" \
  --display-name "$SA_NAME" \
  --project "$PROJECT_ID" || true

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
echo "Service account: $SA_EMAIL"

# 5. Ensure secrets exist in Secret Manager
REQUIRED_SECRETS=(
  SECRET_KEY
  DB_NAME
  DB_USER
  DB_PASSWORD
  DB_HOST
  DB_PORT
  GEMINI_API_KEY
  SERPAPI_API_KEY
  GMAIL_ADDRESS
  GMAIL_APP_PASSWORD
  GMAIL_IMAP_HOST
  DEFAULT_FROM_EMAIL
  EMAIL_HOST
  EMAIL_PORT
  EMAIL_USE_TLS
  EMAIL_HOST_USER
  EMAIL_HOST_PASSWORD
  SEARXNG_INSTANCE_URL
  REDDIT_CLIENT_ID
  REDDIT_CLIENT_SECRET
  REDDIT_USER_AGENT
  PEXELS_API_KEY
  GIPHY_API_KEY
  LINKEDIN_ACCESS_TOKEN
  LINKEDIN_PERSON_URN
  GOOGLE_SHEETS_CREDENTIALS_JSON
  SUPPLIERS_CSV_DATA
)

echo "Checking & updating secrets..."
for s in "${REQUIRED_SECRETS[@]}"; do
  val=$(printenv "$s" || true)
  if [ -z "$val" ]; then
    if gcloud secrets describe "$s" --project "$PROJECT_ID" >/dev/null 2>&1; then
      echo "$s exists in Secret Manager."
    else
      echo "Warning: Secret $s not in env or Secret Manager (will be empty)"
      # Create empty secret to avoid deployment errors
      echo -n "" | gcloud secrets create "$s" --data-file=- --project "$PROJECT_ID" || true
    fi
  else
    if ! gcloud secrets describe "$s" --project "$PROJECT_ID" >/dev/null 2>&1; then
      echo "Creating secret: $s"
      echo -n "$val" | gcloud secrets create "$s" --data-file=- --project "$PROJECT_ID"
    else
      echo "Updating secret: $s"
      echo -n "$val" | gcloud secrets versions add "$s" --data-file=- --project "$PROJECT_ID"
    fi
  fi

  # Grant Cloud Run service account access
  gcloud secrets add-iam-policy-binding "$s" \
    --project "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    >/dev/null 2>&1 || true
done

# 6. Deploy to Cloud Run (connects to Neon DB)
echo "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --service-account "$SA_EMAIL" \
  --set-secrets="\
SECRET_KEY=SECRET_KEY:latest,\
DB_NAME=DB_NAME:latest,\
DB_USER=DB_USER:latest,\
DB_PASSWORD=DB_PASSWORD:latest,\
DB_HOST=DB_HOST:latest,\
DB_PORT=DB_PORT:latest,\
GEMINI_API_KEY=GEMINI_API_KEY:latest,\
SERPAPI_API_KEY=SERPAPI_API_KEY:latest,\
GMAIL_ADDRESS=GMAIL_ADDRESS:latest,\
GMAIL_APP_PASSWORD=GMAIL_APP_PASSWORD:latest,\
GMAIL_IMAP_HOST=GMAIL_IMAP_HOST:latest,\
DEFAULT_FROM_EMAIL=DEFAULT_FROM_EMAIL:latest,\
EMAIL_HOST=EMAIL_HOST:latest,\
EMAIL_PORT=EMAIL_PORT:latest,\
EMAIL_USE_TLS=EMAIL_USE_TLS:latest,\
EMAIL_HOST_USER=EMAIL_HOST_USER:latest,\
EMAIL_HOST_PASSWORD=EMAIL_HOST_PASSWORD:latest,\
SEARXNG_INSTANCE_URL=SEARXNG_INSTANCE_URL:latest,\
REDDIT_CLIENT_ID=REDDIT_CLIENT_ID:latest,\
REDDIT_CLIENT_SECRET=REDDIT_CLIENT_SECRET:latest,\
REDDIT_USER_AGENT=REDDIT_USER_AGENT:latest,\
PEXELS_API_KEY=PEXELS_API_KEY:latest,\
GIPHY_API_KEY=GIPHY_API_KEY:latest,\
LINKEDIN_ACCESS_TOKEN=LINKEDIN_ACCESS_TOKEN:latest,\
LINKEDIN_PERSON_URN=LINKEDIN_PERSON_URN:latest,\
GOOGLE_SHEETS_CREDENTIALS_JSON=GOOGLE_SHEETS_CREDENTIALS_JSON:latest,\
SUPPLIERS_CSV_DATA=SUPPLIERS_CSV_DATA:latest" \
  --set-env-vars="DJANGO_SETTINGS_MODULE=command_center.settings,DEBUG=False,ALLOWED_HOSTS=command-center-uat-6ys7pejqpq-uc.a.run.app,USE_GCS=True,GCS_BUCKET_NAME=kaliagents-media,GCP_PROJECT_ID=$PROJECT_ID" \
  --min-instances=1 \
  --max-instances=1 \
  --cpu-boost \
  --allow-unauthenticated \
  --port=8080 \
  --timeout=300 \
  --memory=1Gi \
  --cpu=1 \
  --project "$PROJECT_ID"

# Show final deployed URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --format='value(status.url)')
echo ""
echo "Deployment complete!"
echo "Service URL: $SERVICE_URL"
echo ""
