#!/bin/bash

# =============================================================================
# Atlas Memory Demo - Setup
# =============================================================================
# Checks prerequisites, installs dependencies, configures backend/.env,
# and starts both servers.
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

ERRORS=()

log_ok()   { echo -e "  ${GREEN}OK${NC}  $1"; }
log_warn() { echo -e "  ${YELLOW}!!${NC}  $1"; }
log_fail() { echo -e "  ${RED}FAIL${NC}  $1"; ERRORS+=("$1"); }
log_info() { echo -e "  ${DIM}..${NC}  $1"; }

echo ""
echo -e "${BOLD}Atlas Memory Demo - Setup${NC}"
echo -e "${DIM}Installs dependencies, configures .env, and starts servers.${NC}"
echo ""

# =============================================================================
# Step 1: Check prerequisites
# =============================================================================

echo -e "${BLUE}[1/4] Checking prerequisites${NC}"

# --- Python (uv manages its own; system Python only needed as fallback) ---
if command -v uv &> /dev/null; then
    # uv auto-installs the right Python version from backend/.python-version
    log_ok "Python (managed by uv)"
elif command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
        log_ok "Python $PY_VERSION"
    else
        log_fail "Python $PY_VERSION found but 3.10+ required (or install uv to auto-manage Python)"
    fi
else
    log_fail "Python 3 not found (install uv from https://docs.astral.sh/uv/ or Python from https://python.org)"
fi

# --- Node ---
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version 2>/dev/null | sed 's/^v//')
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        log_ok "Node.js $NODE_VERSION"
    else
        log_fail "Node.js $NODE_VERSION found but 18+ required"
    fi
else
    log_fail "Node.js not found (install from https://nodejs.org)"
fi

# --- uv ---
if command -v uv &> /dev/null; then
    log_ok "uv $(uv --version 2>/dev/null | head -1 | awk '{print $2}')"
else
    log_info "Installing uv..."
    if curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1; then
        if [ -f "$HOME/.cargo/env" ]; then
            source "$HOME/.cargo/env"
        elif [ -f "$HOME/.local/bin/uv" ]; then
            export PATH="$HOME/.local/bin:$PATH"
        fi
        if command -v uv &> /dev/null; then
            log_ok "uv installed"
        else
            log_warn "uv installed but not in PATH — restart your terminal and re-run ./setup.sh"
        fi
    else
        log_fail "Failed to install uv (see https://docs.astral.sh/uv/)"
    fi
fi

if [ ${#ERRORS[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Fix the issues above and re-run ./setup.sh${NC}"
    exit 1
fi

# =============================================================================
# Step 2: Install dependencies
# =============================================================================

echo ""
echo -e "${BLUE}[2/4] Installing dependencies${NC}"

# Backend (Python)
log_info "Backend dependencies..."
if command -v uv &> /dev/null; then
    (cd backend && uv sync > /dev/null 2>&1) && \
        log_ok "Backend dependencies (uv sync)" || \
        log_fail "Backend install failed"

    # Keep requirements.txt in sync
    if (cd backend && uv pip compile pyproject.toml -o requirements.txt --quiet 2>/dev/null); then
        TEMP_REQ=$(mktemp)
        echo "# AUTO-GENERATED from pyproject.toml — do not edit manually." > "$TEMP_REQ"
        echo "# To update: cd backend && uv pip compile pyproject.toml -o requirements.txt" >> "$TEMP_REQ"
        echo "" >> "$TEMP_REQ"
        cat backend/requirements.txt >> "$TEMP_REQ"
        mv "$TEMP_REQ" backend/requirements.txt
        log_ok "requirements.txt synced"
    fi

    IMPORT_ERR=$(cd backend && uv run python -c "from app.main import app" 2>&1)
    if [ $? -eq 0 ]; then
        log_ok "Backend imports verified"
    else
        log_fail "Backend import check failed"
        echo -e "       ${DIM}${IMPORT_ERR}${NC}" | tail -5 | sed 's/^/       /'
    fi
fi

# Frontend (Node.js)
log_info "Frontend dependencies..."
if [ -f "frontend/yarn.lock" ] && command -v yarn &> /dev/null; then
    (cd frontend && yarn install --non-interactive --silent > /dev/null 2>&1) && \
        log_ok "Frontend dependencies (yarn)" || \
        log_fail "Frontend install failed"
elif command -v npm &> /dev/null; then
    (cd frontend && npm install --no-fund --no-audit --loglevel=error > /dev/null 2>&1) && \
        log_ok "Frontend dependencies (npm)" || \
        log_fail "Frontend install failed"
else
    log_fail "No package manager found (install yarn or npm)"
fi

# =============================================================================
# Step 3: Configure Elastic connection
# =============================================================================

echo ""
echo -e "${BLUE}[3/4] Configuring Elastic connection${NC}"

if [ ! -f "backend/.env" ]; then
    cp backend/.env.example backend/.env
    log_info "Created backend/.env from template"
fi

EXISTING_KIBANA=$(grep -s '^KIBANA_URL=.\+' backend/.env | head -1)
EXISTING_ES=$(grep -s '^ELASTICSEARCH_URL=.\+' backend/.env | head -1)
EXISTING_KEY=$(grep -s '^ELASTIC_API_KEY=.\+' backend/.env | head -1)

if [ -n "$EXISTING_KIBANA" ] && [ -n "$EXISTING_ES" ] && [ -n "$EXISTING_KEY" ]; then
    log_ok "Elastic credentials found in backend/.env"
else
    log_warn "Elastic credentials not set in backend/.env"
    echo ""
    echo -e "  Edit ${BOLD}backend/.env${NC} and set:"
    echo -e "    ${DIM}ELASTICSEARCH_URL=https://your-cluster.es.cloud.es.io${NC}"
    echo -e "    ${DIM}KIBANA_URL=https://your-cluster.kb.cloud.es.io${NC}"
    echo -e "    ${DIM}ELASTIC_API_KEY=your-api-key${NC}"
    echo ""
    echo -e "  ${DIM}Tip: Create a free cluster at https://cloud.elastic.co${NC}"
    echo -e "  ${DIM}Then re-run ./setup.sh to verify, or proceed to step 4 below.${NC}"
    echo ""
fi

# =============================================================================
# Step 4: Start servers
# =============================================================================

echo -e "${BLUE}[4/4] Starting servers${NC}"

if [ -n "$EXISTING_KIBANA" ] && [ -n "$EXISTING_ES" ] && [ -n "$EXISTING_KEY" ]; then
    log_info "Starting backend and frontend..."
    ./dev start 2>&1 | while IFS= read -r line; do
        echo -e "       ${DIM}${line}${NC}"
    done

    BACKEND_PORT="8001"
    FRONTEND_PORT="3000"
    [ -f ".dev-pids/backend.port" ] && BACKEND_PORT=$(cat .dev-pids/backend.port)
    [ -f ".dev-pids/frontend.port" ] && FRONTEND_PORT=$(cat .dev-pids/frontend.port)

    BACKEND_OK=false
    for i in $(seq 1 20); do
        if curl -s --max-time 1 "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
            BACKEND_OK=true
            break
        fi
        sleep 0.5
    done

    if [ "$BACKEND_OK" = true ]; then
        log_ok "Backend running on port $BACKEND_PORT"
    else
        log_fail "Backend failed to start on port $BACKEND_PORT"
        if [ -f ".dev-logs/backend.log" ]; then
            echo -e "       ${DIM}Last 10 lines of backend log:${NC}"
            tail -10 .dev-logs/backend.log 2>/dev/null | while IFS= read -r line; do
                echo -e "       ${DIM}${line}${NC}"
            done
        fi
    fi

    FRONTEND_OK=false
    for i in $(seq 1 20); do
        if curl -s --max-time 1 "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
            FRONTEND_OK=true
            break
        fi
        sleep 0.5
    done

    if [ "$FRONTEND_OK" = true ]; then
        log_ok "Frontend running on port $FRONTEND_PORT"
    else
        log_warn "Frontend starting on port $FRONTEND_PORT (may take a moment)"
    fi

    # Configure Playwright MCP for Claude Code (browser tools)
    MCP_JSON="$SCRIPT_DIR/.mcp.json"
    if [ ! -f "$MCP_JSON" ] || ! grep -q '"playwright"' "$MCP_JSON" 2>/dev/null; then
        if command -v npx &> /dev/null && npx --yes @playwright/mcp@latest --version > /dev/null 2>&1; then
            if [ -f "$MCP_JSON" ]; then
                node -e "
                    const fs = require('fs');
                    const existing = JSON.parse(fs.readFileSync('$MCP_JSON', 'utf8'));
                    if (!existing.mcpServers) existing.mcpServers = {};
                    existing.mcpServers.playwright = { command: 'npx', args: ['@playwright/mcp@latest'] };
                    fs.writeFileSync('$MCP_JSON', JSON.stringify(existing, null, 2) + '\n');
                " 2>/dev/null && log_ok "Playwright MCP configured in .mcp.json"
            else
                cat > "$MCP_JSON" << 'MCPJSON'
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
MCPJSON
                log_ok "Created .mcp.json with Playwright MCP"
            fi
        fi
    else
        log_ok "Playwright MCP already configured"
    fi
else
    log_warn "Skipping server start — set Elastic credentials first (step 3)"
    FRONTEND_PORT="3000"
    BACKEND_PORT="8001"
fi

# =============================================================================
# Done
# =============================================================================

echo ""
if [ ${#ERRORS[@]} -gt 0 ]; then
    echo -e "${YELLOW}${BOLD}Setup completed with warnings.${NC}"
else
    echo -e "${GREEN}${BOLD}Setup complete!${NC}"
fi
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo ""

if [ -z "$EXISTING_KIBANA" ] || [ -z "$EXISTING_ES" ] || [ -z "$EXISTING_KEY" ]; then
    echo -e "  ${YELLOW}1. Configure credentials${NC}: edit ${BOLD}backend/.env${NC} then re-run ${BOLD}./setup.sh${NC}"
    echo ""
fi

echo -e "  ${BOLD}Seed demo data${NC} (required on first run — takes ~1 min, also mints per-user DLS API keys):"
echo -e "    ${DIM}cd backend && uv run python -m scripts.atlas.reset_and_seed${NC}"
echo ""
echo -e "  ${BOLD}Open the demo${NC}:"
echo -e "    ${DIM}http://localhost:${FRONTEND_PORT}${NC}"
echo ""
echo -e "  ${BOLD}Read the demo guide${NC}:  ATLAS.md"
echo ""
echo -e "  ${DIM}Stop:  ./dev stop${NC}"
echo -e "  ${DIM}Logs:  ./dev logs-snapshot${NC}"
echo ""

cat > .setup-complete << MARKER
# Setup completed successfully
# This file is created by setup.sh
timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
MARKER
