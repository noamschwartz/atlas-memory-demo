#!/bin/bash
# =============================================================================
# Deploy to Cloud Run with Sidecars
# 
# ✅ THIS IS THE RECOMMENDED WAY TO DEPLOY TO CLOUD RUN
#
# Usage: ./deploy/deploy-cloudrun.sh
#
# Prerequisites:
#   1. gcloud CLI authenticated: gcloud auth login
#   2. Docker running
#   3. Environment variables set (or update defaults below)
#
# This script:
#   1. Builds all 3 Docker images (nginx, fastapi, otel-collector)
#   2. Pushes them to Artifact Registry
#   3. Generates service.yaml with your credentials
#   4. Deploys to Cloud Run
#
# ⚠️  Do NOT use cloudbuild.yaml or Dockerfile.cloudrun (all-in-one approach)
#     Those have reliability issues. Always use this sidecar script.
# =============================================================================

set -e

# ============================================================================
# CONFIGURATION - Update these for your deployment
# ============================================================================

# GCP Configuration
PROJECT_ID="${GCP_PROJECT_ID:-elastic-sa}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-my-demo}"
REPO="us-central1-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy"

# Base path for the app (e.g., /ecommerce/, /chat/, /demo/)
BASE_PATH="${BASE_PATH:-/demo/}"

# Elasticsearch Configuration (Data Cluster)
ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-}"
ELASTIC_API_KEY="${ELASTIC_API_KEY:-}"
SEARCH_INDEX="${SEARCH_INDEX:-products}"

# Monitoring Cluster (for APM traces - can be same as data cluster)
MONITORING_ES_URL="${MONITORING_ELASTICSEARCH_URL:-}"
MONITORING_API_KEY="${MONITORING_ELASTIC_API_KEY:-}"

# APM/OTel Configuration
OTEL_ENDPOINT="${OTEL_EXPORTER_OTLP_ENDPOINT:-}"
APM_TOKEN="${ELASTIC_APM_SECRET_TOKEN:-}"

# ============================================================================
# VALIDATION
# ============================================================================

echo "=========================================="
echo "Cloud Run Deployment: $SERVICE_NAME"
echo "=========================================="

# Check required credentials
missing_vars=()
[ -z "$ELASTICSEARCH_URL" ] && missing_vars+=("ELASTICSEARCH_URL")
[ -z "$ELASTIC_API_KEY" ] && missing_vars+=("ELASTIC_API_KEY")

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "❌ Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Set them and re-run, or export them before running this script:"
    echo "   export ELASTICSEARCH_URL='https://your-cluster.elastic-cloud.com'"
    echo "   export ELASTIC_API_KEY='your-api-key'"
    exit 1
fi

# Optional: Use data cluster for monitoring if not specified
[ -z "$MONITORING_ES_URL" ] && MONITORING_ES_URL="$ELASTICSEARCH_URL"
[ -z "$MONITORING_API_KEY" ] && MONITORING_API_KEY="$ELASTIC_API_KEY"

# Generate unique tag
TAG=$(date +%Y%m%d-%H%M%S)

echo ""
echo "Configuration:"
echo "  Project:      $PROJECT_ID"
echo "  Region:       $REGION"
echo "  Service:      $SERVICE_NAME"
echo "  Base Path:    $BASE_PATH"
echo "  Tag:          $TAG"
echo "  ES URL:       ${ELASTICSEARCH_URL:0:50}..."
echo ""

# ============================================================================
# BUILD DOCKER IMAGES
# ============================================================================

echo ">>> Building Docker images..."

echo "  [1/3] Building Nginx (frontend)..."
# CRITICAL: VITE_API_URL must match BASE_PATH (without trailing slash)
# The shared load balancer only routes /{basepath}/* to this service.
# Without this, /api/* requests go to the default landing page and return HTML!
# e.g., BASE_PATH=/demo/ → VITE_API_URL=/demo
API_URL_PREFIX="${BASE_PATH%/}"  # Remove trailing slash
docker build \
    -f deploy/Dockerfile.nginx \
    -t "${REPO}/${SERVICE_NAME}-nginx:${TAG}" \
    --build-arg VITE_BASE_PATH="${BASE_PATH}" \
    --build-arg VITE_OTEL_ENDPOINT="${BASE_PATH}v1/traces" \
    --build-arg VITE_API_URL="${API_URL_PREFIX}" \
    --platform linux/amd64 \
    .

echo "  [2/3] Building FastAPI (backend)..."
docker build \
    -f deploy/Dockerfile.fastapi \
    -t "${REPO}/${SERVICE_NAME}-fastapi:${TAG}" \
    --platform linux/amd64 \
    .

echo "  [3/3] Building OTel Collector..."
docker build \
    -f deploy/Dockerfile.otel-collector \
    -t "${REPO}/${SERVICE_NAME}-otel:${TAG}" \
    --platform linux/amd64 \
    .

# ============================================================================
# PUSH TO ARTIFACT REGISTRY
# ============================================================================

echo ""
echo ">>> Pushing images to Artifact Registry..."

docker push "${REPO}/${SERVICE_NAME}-nginx:${TAG}"
docker push "${REPO}/${SERVICE_NAME}-fastapi:${TAG}"
docker push "${REPO}/${SERVICE_NAME}-otel:${TAG}"

# ============================================================================
# GENERATE SERVICE.YAML
# ============================================================================

echo ""
echo ">>> Generating service configuration..."

SERVICE_YAML=$(mktemp)

# Important: Replace longer/more specific strings FIRST to avoid partial matches
cat deploy/service.yaml | \
    sed "s|YOUR_SERVICE_NAME|${SERVICE_NAME}|g" | \
    sed "s|YOUR_PROJECT_ID|${PROJECT_ID}|g" | \
    sed "s|YOUR_TEAM|search-specialist|g" | \
    sed "s|YOUR_EMAIL|$(whoami)|g" | \
    sed "s|YOUR_PROJECT|${SERVICE_NAME}|g" | \
    sed "s|${SERVICE_NAME}-nginx:PLACEHOLDER|${SERVICE_NAME}-nginx:${TAG}|g" | \
    sed "s|${SERVICE_NAME}-fastapi:PLACEHOLDER|${SERVICE_NAME}-fastapi:${TAG}|g" | \
    sed "s|${SERVICE_NAME}-otel:PLACEHOLDER|${SERVICE_NAME}-otel:${TAG}|g" | \
    sed "s|MONITORING_ELASTICSEARCH_URL_PLACEHOLDER|${MONITORING_ES_URL}|g" | \
    sed "s|MONITORING_ELASTIC_API_KEY_PLACEHOLDER|${MONITORING_API_KEY}|g" | \
    sed "s|ELASTICSEARCH_URL_PLACEHOLDER|${ELASTICSEARCH_URL}|g" | \
    sed "s|ELASTIC_API_KEY_PLACEHOLDER|${ELASTIC_API_KEY}|g" | \
    sed "s|OTEL_ENDPOINT_PLACEHOLDER|${OTEL_ENDPOINT}|g" | \
    sed "s|APM_TOKEN_PLACEHOLDER|${APM_TOKEN}|g" \
    > "$SERVICE_YAML"

echo "Service config written to: $SERVICE_YAML"

# ============================================================================
# DEPLOY TO CLOUD RUN
# ============================================================================

echo ""
echo ">>> Deploying to Cloud Run..."

gcloud run services replace "$SERVICE_YAML" \
    --region="${REGION}" \
    --project="${PROJECT_ID}"

# Cleanup
rm -f "$SERVICE_YAML"

# ============================================================================
# SET CLOUD RUN INVOKER PERMISSION
# ============================================================================

echo ""
echo ">>> Setting Cloud Run invoker permission..."
echo "   (Required for Load Balancer to reach Cloud Run through IAP)"

# This is REQUIRED and NOT a security risk because:
# - ingress: internal-and-cloud-load-balancing blocks direct access
# - All traffic must go through Load Balancer which enforces IAP
# - Without this, authenticated users get 403 Forbidden
gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --quiet 2>/dev/null || echo "   (Permission may already exist)"

# ============================================================================
# DONE
# ============================================================================

echo ""
echo "=========================================="
echo "✅ Deployment complete!"
echo ""
echo "🔒 IMPORTANT: Set up IAP authentication (REQUIRED)"
echo ""
echo "The service is deployed with internal-only ingress + invoker permission."
echo "You MUST set up IAP to access it. Run these commands:"
echo ""
echo "  # 1. Create NEG and Backend Service (one-time setup)"
echo "  gcloud compute network-endpoint-groups create ${SERVICE_NAME}-neg \\"
echo "      --region=${REGION} --network-endpoint-type=serverless \\"
echo "      --cloud-run-service=${SERVICE_NAME} --project=${PROJECT_ID}"
echo ""
echo "  gcloud compute backend-services create ${SERVICE_NAME}-backend \\"
echo "      --global --protocol=HTTP --project=${PROJECT_ID}"
echo ""
echo "  gcloud compute backend-services add-backend ${SERVICE_NAME}-backend \\"
echo "      --global --network-endpoint-group=${SERVICE_NAME}-neg \\"
echo "      --network-endpoint-group-region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "  gcloud compute backend-services update ${SERVICE_NAME}-backend \\"
echo "      --global --iap=enabled --project=${PROJECT_ID}"
echo ""
echo "  # 2. Add to URL map (edit and import)"
echo "  See docs/DEPLOYMENT.md for URL map configuration"
echo ""
echo "  # NOTE: elastic.co domain access is granted at project level in elastic-sa"
echo "  # For other projects, grant access with:"
echo "  # gcloud iap web add-iam-policy-binding --resource-type=backend-services \\"
echo "  #     --service=${SERVICE_NAME}-backend --member='domain:elastic.co' \\"
echo "  #     --role='roles/iap.httpsResourceAccessor' --project=${PROJECT_ID}"
echo ""
echo "After IAP setup, access at: https://demos.gcp.elasticsa.co${BASE_PATH}"
echo ""
echo "View logs:"
echo "  gcloud run services logs read ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo "=========================================="
