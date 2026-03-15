#!/usr/bin/env bash
# deploy.sh — Deploy AI Redaction to Azure
# Usage: ./deploy.sh [dev|prod] [--infra-only | --app-only | --skip-frontend]
#
# Steps:
#   1. Deploy Bicep infrastructure (subscription-scoped)
#   2. Build & push backend Docker image to ACR
#   3. Build & deploy frontend to Static Web Apps
#
# Prerequisites:
#   - Azure CLI (az) logged in with subscription set
#   - Docker daemon running (for --app or full deploy)
#   - pnpm installed (for --frontend or full deploy)
#   - SWA CLI: npm i -g @azure/static-web-apps-cli (for --frontend or full deploy)

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
ENVIRONMENT="${1:-dev}"
INFRA_ONLY=false
APP_ONLY=false
SKIP_FRONTEND=false

# Parse flags
for arg in "${@:2}"; do
  case "$arg" in
    --infra-only)    INFRA_ONLY=true ;;
    --app-only)      APP_ONLY=true ;;
    --skip-frontend) SKIP_FRONTEND=true ;;
    *)               echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# ── Resolve param file ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAM_FILE="${SCRIPT_DIR}/infra/${ENVIRONMENT}.bicepparam"
BICEP_FILE="${SCRIPT_DIR}/infra/main.bicep"

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
  echo "ERROR: Environment must be 'dev' or 'prod' (got '${ENVIRONMENT}')"
  exit 1
fi

if [[ ! -f "$PARAM_FILE" ]]; then
  echo "ERROR: Parameter file not found: ${PARAM_FILE}"
  exit 1
fi

# ── Colour helpers ─────────────────────────────────────────────────────────────
BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RESET='\033[0m'

log()  { echo -e "${CYAN}[deploy]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }
step() { echo -e "\n${BOLD}══ $* ══${RESET}"; }

# ── Preflight checks ───────────────────────────────────────────────────────────
step "Preflight"

if ! command -v az &>/dev/null; then
  echo "ERROR: Azure CLI not found. Install from https://aka.ms/installazurecliwindows"
  exit 1
fi

ACCOUNT=$(az account show --query "{name:name,id:id,user:user.name}" -o json 2>/dev/null || true)
if [[ -z "$ACCOUNT" ]]; then
  echo "ERROR: Not logged in to Azure CLI. Run: az login"
  exit 1
fi

SUBSCRIPTION_NAME=$(echo "$ACCOUNT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['name'])")
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
USER_NAME=$(echo "$ACCOUNT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['user'])")

log "Subscription : ${SUBSCRIPTION_NAME} (${SUBSCRIPTION_ID})"
log "User         : ${USER_NAME}"
log "Environment  : ${ENVIRONMENT}"
log "Param file   : ${PARAM_FILE}"

if [[ "$ENVIRONMENT" == "prod" ]]; then
  warn "You are deploying to PRODUCTION."
  read -r -p "  Type 'yes' to confirm: " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# ── Step 1: Infrastructure ─────────────────────────────────────────────────────
if [[ "$APP_ONLY" == false ]]; then
  step "Infrastructure — az deployment sub create"

  DEPLOYMENT_NAME="redactor-${ENVIRONMENT}-$(date -u +%Y%m%dT%H%M%S)"

  log "Starting deployment: ${DEPLOYMENT_NAME}"

  DEPLOY_OUTPUT=$(az deployment sub create \
    --name "$DEPLOYMENT_NAME" \
    --location "uksouth" \
    --template-file "$BICEP_FILE" \
    --parameters "$PARAM_FILE" \
    --query "properties.outputs" \
    -o json)

  # Extract outputs
  RESOURCE_GROUP=$(echo "$DEPLOY_OUTPUT"  | python3 -c "import sys,json; print(json.load(sys.stdin)['resourceGroupName']['value'])")
  ACR_LOGIN_SERVER=$(echo "$DEPLOY_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['acrLoginServer']['value'])")
  APP_SERVICE_URL=$(echo "$DEPLOY_OUTPUT"  | python3 -c "import sys,json; print(json.load(sys.stdin)['appServiceUrl']['value'])")
  SWA_URL=$(echo "$DEPLOY_OUTPUT"          | python3 -c "import sys,json; print(json.load(sys.stdin)['swaUrl']['value'])")
  COSMOS_ENDPOINT=$(echo "$DEPLOY_OUTPUT"  | python3 -c "import sys,json; print(json.load(sys.stdin)['cosmosEndpoint']['value'])")
  FOUNDRY_ENDPOINT=$(echo "$DEPLOY_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['foundryEndpoint']['value'])")

  ok "Infrastructure deployed"
  log "  Resource group   : ${RESOURCE_GROUP}"
  log "  ACR              : ${ACR_LOGIN_SERVER}"
  log "  App Service URL  : ${APP_SERVICE_URL}"
  log "  SWA URL          : ${SWA_URL}"
else
  # --app-only: resolve names from existing deployment
  step "Resolving existing infrastructure"

  APP_NAME="redactor"
  REGION_ABBREV="uks"
  RESOURCE_GROUP="rg-${APP_NAME}-${ENVIRONMENT}-${REGION_ABBREV}"

  ACR_NAME="cr${APP_NAME}${ENVIRONMENT}${REGION_ABBREV}"
  ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)
  APP_SERVICE_URL=$(az webapp show --name "app-${APP_NAME}-${ENVIRONMENT}-${REGION_ABBREV}" \
    --resource-group "$RESOURCE_GROUP" --query defaultHostName -o tsv)
  APP_SERVICE_URL="https://${APP_SERVICE_URL}"
  SWA_URL=$(az staticwebapp show --name "stapp-${APP_NAME}-${ENVIRONMENT}-${REGION_ABBREV}" \
    --resource-group "$RESOURCE_GROUP" --query defaultHostname -o tsv)
  SWA_URL="https://${SWA_URL}"

  ok "Resolved existing resources"
  log "  Resource group   : ${RESOURCE_GROUP}"
  log "  ACR              : ${ACR_LOGIN_SERVER}"
fi

# ── Step 2: Backend Docker image ───────────────────────────────────────────────
if [[ "$INFRA_ONLY" == false ]]; then
  step "Backend — Build & push Docker image"

  if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker not found. Install Docker Desktop or Docker Engine."
    exit 1
  fi

  IMAGE_TAG="${ACR_LOGIN_SERVER}/redactor-api:latest"

  log "Logging in to ACR: ${ACR_LOGIN_SERVER}"
  az acr login --name "${ACR_LOGIN_SERVER%%.*}"

  log "Building image: ${IMAGE_TAG}"
  docker build \
    --platform linux/amd64 \
    --file "${SCRIPT_DIR}/backend/Dockerfile" \
    --tag "$IMAGE_TAG" \
    "${SCRIPT_DIR}/backend"

  log "Pushing image: ${IMAGE_TAG}"
  docker push "$IMAGE_TAG"

  ok "Image pushed: ${IMAGE_TAG}"

  # Restart the App Service to pull the new image
  APP_SERVICE_NAME="app-redactor-${ENVIRONMENT}-uks"
  log "Restarting App Service: ${APP_SERVICE_NAME}"
  az webapp restart --name "$APP_SERVICE_NAME" --resource-group "$RESOURCE_GROUP"
  ok "App Service restarted"
fi

# ── Step 3: Frontend SWA ───────────────────────────────────────────────────────
if [[ "$INFRA_ONLY" == false && "$SKIP_FRONTEND" == false ]]; then
  step "Frontend — Build & deploy to Static Web Apps"

  if ! command -v pnpm &>/dev/null; then
    warn "pnpm not found — skipping frontend deploy. Install with: npm i -g pnpm"
  elif ! command -v swa &>/dev/null; then
    warn "SWA CLI not found — skipping frontend deploy. Install with: npm i -g @azure/static-web-apps-cli"
  else
    SWA_NAME="stapp-redactor-${ENVIRONMENT}-uks"
    DEPLOY_TOKEN=$(az staticwebapp secrets list \
      --name "$SWA_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --query "properties.apiKey" -o tsv)

    log "Installing frontend dependencies"
    (cd "${SCRIPT_DIR}/frontend" && pnpm install --frozen-lockfile)

    log "Building frontend"
    (cd "${SCRIPT_DIR}/frontend" && pnpm build)

    log "Deploying to Static Web Apps: ${SWA_NAME}"
    swa deploy "${SCRIPT_DIR}/frontend/dist" \
      --deployment-token "$DEPLOY_TOKEN" \
      --env production

    ok "Frontend deployed: ${SWA_URL}"
  fi
fi

# ── Summary ────────────────────────────────────────────────────────────────────
step "Done"
echo -e "  ${BOLD}Backend${RESET}  : ${APP_SERVICE_URL:-<skipped>}"
echo -e "  ${BOLD}Frontend${RESET} : ${SWA_URL:-<skipped>}"
