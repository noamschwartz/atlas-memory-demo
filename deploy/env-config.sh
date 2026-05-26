#!/bin/bash
# =============================================================================
# Environment Variable Configuration
# =============================================================================
# This file defines all environment variables used by the deployment.
# 
# To add a new variable:
#   1. Add it to REQUIRED_VARS or OPTIONAL_VARS array below
#   2. Update the get_description() and get_default() functions
#   3. Update .env.example
#
# The deploy script sources this file and automatically:
#   - Validates required vars are set
#   - Shows helpful error messages with descriptions
#   - Applies defaults for optional vars
#
# COMPATIBILITY: Works with bash 3.x (macOS default) - no associative arrays
# =============================================================================

# -----------------------------------------------------------------------------
# REQUIRED VARIABLES - Deployment will fail if these are not set
# -----------------------------------------------------------------------------
REQUIRED_VARS=(
    "ELASTICSEARCH_URL"
    "ELASTIC_API_KEY"
)

# -----------------------------------------------------------------------------
# OPTIONAL VARIABLES - Have sensible defaults, can be overridden
# -----------------------------------------------------------------------------
OPTIONAL_VARS=(
    "GCP_PROJECT_ID"
    "GCP_REGION"
    "SERVICE_NAME"
    "BASE_PATH"
    "SEARCH_INDEX"
    "MONITORING_ELASTICSEARCH_URL"
    "MONITORING_ELASTIC_API_KEY"
    "OTEL_EXPORTER_OTLP_ENDPOINT"
    "ELASTIC_APM_SECRET_TOKEN"
    "MIN_INSTANCES"
    "MAX_INSTANCES"
)

# -----------------------------------------------------------------------------
# Get description for a variable (bash 3.x compatible)
# -----------------------------------------------------------------------------
get_description() {
    local var="$1"
    case "$var" in
        ELASTICSEARCH_URL)           echo "Elasticsearch URL (e.g., https://my-cluster.es.us-central1.gcp.cloud.es.io)" ;;
        ELASTIC_API_KEY)             echo "API key for Elasticsearch with search permissions" ;;
        GCP_PROJECT_ID)              echo "GCP project ID for deployment" ;;
        GCP_REGION)                  echo "GCP region for Cloud Run" ;;
        SERVICE_NAME)                echo "Cloud Run service name" ;;
        BASE_PATH)                   echo "URL base path (e.g., /demo/, /ecommerce/)" ;;
        SEARCH_INDEX)                echo "Elasticsearch index for data" ;;
        MONITORING_ELASTICSEARCH_URL) echo "Elasticsearch URL for APM/traces (defaults to ELASTICSEARCH_URL)" ;;
        MONITORING_ELASTIC_API_KEY)  echo "API key for monitoring cluster (defaults to ELASTIC_API_KEY)" ;;
        OTEL_EXPORTER_OTLP_ENDPOINT) echo "Elastic APM OTLP endpoint (leave empty to disable tracing)" ;;
        ELASTIC_APM_SECRET_TOKEN)    echo "APM secret token for authentication" ;;
        MIN_INSTANCES)               echo "Minimum Cloud Run instances (0 = scale to zero)" ;;
        MAX_INSTANCES)               echo "Maximum Cloud Run instances" ;;
        *)                           echo "No description" ;;
    esac
}

# -----------------------------------------------------------------------------
# Get default value for a variable (bash 3.x compatible)
# -----------------------------------------------------------------------------
get_default() {
    local var="$1"
    case "$var" in
        GCP_PROJECT_ID)   echo "elastic-sa" ;;
        GCP_REGION)       echo "us-central1" ;;
        SERVICE_NAME)     echo "my-demo" ;;
        BASE_PATH)        echo "/demo/" ;;
        SEARCH_INDEX)     echo "products" ;;
        MIN_INSTANCES)    echo "0" ;;
        MAX_INSTANCES)    echo "1" ;;
        *)                echo "" ;;
    esac
}

# -----------------------------------------------------------------------------
# VALIDATION FUNCTION - Call this from deploy script
# -----------------------------------------------------------------------------
validate_env_vars() {
    local missing=()
    local warnings=()
    
    # Check required vars
    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ]; then
            missing+=("$var")
        fi
    done
    
    # If any required vars missing, show error and exit
    if [ ${#missing[@]} -gt 0 ]; then
        echo ""
        echo "❌ Missing required environment variables:"
        echo ""
        for var in "${missing[@]}"; do
            echo "   $var"
            echo "      $(get_description "$var")"
            echo ""
        done
        echo "Set them in your environment or .env file:"
        echo ""
        for var in "${missing[@]}"; do
            echo "   export $var='your-value'"
        done
        echo ""
        echo "Or copy .env.example to .env and fill in values:"
        echo "   cp .env.example .env"
        echo ""
        return 1
    fi
    
    # Apply defaults for optional vars
    for var in "${OPTIONAL_VARS[@]}"; do
        if [ -z "${!var}" ]; then
            local default_val=$(get_default "$var")
            if [ -n "$default_val" ]; then
                export "$var"="$default_val"
            fi
        fi
    done
    
    # Special handling: MONITORING_* defaults to ELASTICSEARCH_*
    [ -z "$MONITORING_ELASTICSEARCH_URL" ] && export MONITORING_ELASTICSEARCH_URL="$ELASTICSEARCH_URL"
    [ -z "$MONITORING_ELASTIC_API_KEY" ] && export MONITORING_ELASTIC_API_KEY="$ELASTIC_API_KEY"
    
    # Warnings for recommended but missing vars
    if [ -z "$OTEL_EXPORTER_OTLP_ENDPOINT" ]; then
        warnings+=("OTEL_EXPORTER_OTLP_ENDPOINT not set - tracing will be disabled")
    fi
    
    if [ ${#warnings[@]} -gt 0 ]; then
        echo ""
        echo "⚠️  Warnings:"
        for warning in "${warnings[@]}"; do
            echo "   - $warning"
        done
        echo ""
    fi
    
    return 0
}

# -----------------------------------------------------------------------------
# PRINT CONFIG FUNCTION - Shows current configuration
# -----------------------------------------------------------------------------
print_config() {
    echo ""
    echo "Configuration:"
    echo "  GCP Project:     $GCP_PROJECT_ID"
    echo "  Region:          $GCP_REGION"
    echo "  Service:         $SERVICE_NAME"
    echo "  Base Path:       $BASE_PATH"
    echo "  ES URL:          ${ELASTICSEARCH_URL:0:50}..."
    echo "  Monitoring URL:  ${MONITORING_ELASTICSEARCH_URL:0:50}..."
    echo "  OTel Endpoint:   ${OTEL_EXPORTER_OTLP_ENDPOINT:-<not set - tracing disabled>}"
    echo "  Scaling:         $MIN_INSTANCES-$MAX_INSTANCES instances"
    echo ""
}

# -----------------------------------------------------------------------------
# URL MAP VALIDATION - Check if BASE_PATH exists in the load balancer URL map
# -----------------------------------------------------------------------------
# The shared load balancer (demos.gcp.elasticsa.co) routes paths to backends:
#   /template/*   → elastic-agent-template-backend
#   /ecommerce/*  → search-otel-ubi-backend
#   /demo/*       → (default)
#
# Your BASE_PATH must match an existing route OR you need to add a new one.
# -----------------------------------------------------------------------------

URL_MAP_NAME="elastic-demos-gateway"

validate_url_map() {
    # Only validate if we're in elastic-sa project
    if [ "$GCP_PROJECT_ID" != "elastic-sa" ]; then
        return 0  # Skip validation for other projects
    fi
    
    # Check if gcloud is available
    if ! command -v gcloud &> /dev/null; then
        echo "⚠️  gcloud not found - skipping URL map validation"
        return 0
    fi
    
    # Get the path without trailing slash for matching
    local path_prefix="${BASE_PATH%/}"
    
    # Query URL map for matching paths
    local url_map_paths
    url_map_paths=$(gcloud compute url-maps describe "$URL_MAP_NAME" \
        --project="$GCP_PROJECT_ID" \
        --format="value(pathMatchers.pathRules.paths.flatten())" 2>/dev/null || echo "")
    
    if [ -z "$url_map_paths" ]; then
        echo "⚠️  Could not query URL map - skipping validation"
        return 0
    fi
    
    # Check if our path exists
    if echo "$url_map_paths" | grep -q "^${path_prefix}$\|^${path_prefix}/\*$"; then
        echo "✅ BASE_PATH '${BASE_PATH}' found in URL map"
        return 0
    else
        echo ""
        echo "⚠️  WARNING: BASE_PATH '${BASE_PATH}' not found in URL map!"
        echo ""
        echo "   The load balancer won't route traffic to your service."
        echo "   Available paths in the URL map:"
        echo "$url_map_paths" | sed 's/^/      /'
        echo ""
        echo "   Options:"
        echo "   1. Change BASE_PATH to match an existing path (e.g., /template/)"
        echo "   2. Add your path to the URL map (see docs/DEPLOYMENT.md)"
        echo ""
        read -p "   Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi
    
    return 0
}

# Helper function to list available URL map paths
list_url_map_paths() {
    echo "Available paths in $URL_MAP_NAME:"
    gcloud compute url-maps describe "$URL_MAP_NAME" \
        --project="${GCP_PROJECT_ID:-elastic-sa}" \
        --format="yaml(pathMatchers.pathRules)" 2>/dev/null | \
        grep -E "^\s+-\s+/" | sed 's/^/  /'
}

# -----------------------------------------------------------------------------
# CLI HELP
# -----------------------------------------------------------------------------
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Usage: This script is sourced by deploy-cloudrun.sh"
    echo ""
    echo "Environment variables are defined in:"
    echo "  - REQUIRED_VARS: Must be set for deployment"
    echo "  - OPTIONAL_VARS: Have defaults, can be overridden"
    echo ""
    echo "To add a new variable:"
    echo "  1. Add to REQUIRED_VARS or OPTIONAL_VARS array"
    echo "  2. Update get_description() and get_default() functions"
    echo "  3. Update .env.example"
    echo ""
    echo "URL Map paths (for elastic-sa project):"
    list_url_map_paths
fi
