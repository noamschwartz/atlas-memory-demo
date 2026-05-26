# Project Rules

> **Single Source of Truth** for AI coding assistants (Claude Code, Cursor, etc.)
> `.cursorrules` points here - no need to maintain two files.

---

## MANDATORY: Run On First Message

> **You MUST complete ALL of these checks before responding to the user's first message.**
> Do NOT engage with the user's request until these steps are done.
> If the user says "hello", run onboarding first, then greet them.

### Step 1: Run Session Summary
Run `./dev session` to get the full environment status in one command. This checks:
- Setup completion, hive-mind, beads, browser tools
- Server status and health
- Config (Elasticsearch, Kibana, search index, Agent ID, API key, OTel, LLM proxy)
- Data availability (search fields)
- Customer context files
- Session type (new vs returning)

Review the output and note any issues (e.g. hive-mind empty, agent not set).

### Step 2: Fix Critical Issues
- **Hive Mind empty** → Ask: "The Hive Mind context is missing. Would you like me to run `git submodule update --init` to download it?"
- **Setup not complete** → Run `./setup.sh` to configure the environment. If it fails, check `./dev status` and `backend/.env` to see if the environment is already functional.

### Step 3: Check Issue Tracker (if beads exists)
If `./dev session` shows beads is configured, run:
```bash
bd ready                       # What can I work on? (no blockers)
bd list --status in_progress   # Active work from previous sessions?
bd blocked                     # What's stuck and why
```
This is your primary source of truth for what needs doing — it survives session restarts.
See the **Issue Tracking with Beads** section below for full workflow.

### Step 4: Determine Session Type
- **`DEMO_PLAN.md` exists** (shown in session output) → Returning session. Read it for context, then `bd ready` to pick up where the last session left off.
- **`DEMO_PLAN.md` does NOT exist** → New demo session. Read and follow `docs/prompts/WELCOME_PROMPT.md`.

### Step 5: Report to User
After completing the above, briefly tell the user what you found (environment status, open issues, session type) and ask how they'd like to proceed.

---

## Hive Mind Integration

This project uses a shared knowledge base at `./hive-mind` (git submodule).

### ALWAYS Index These Directories
- `./hive-mind/patterns/` - Reusable architecture patterns
- `./hive-mind/troubleshooting/` - Bug fixes and solutions
- `./hive-mind/meta/` - Workflows and AI guidance

### Before Generating New Code
1. **CHECK** `./hive-mind/patterns/` for existing solutions
2. **REUSE** patterns rather than inventing new approaches
3. **FOLLOW** the established conventions in existing patterns

### After Making Changes (Before PRs)
1. **RUN** `./dev verify-template` — checks route integrity, frontend↔backend contract, page completeness
2. **FIX** any new failures before committing (existing failures are tracked in beads)
3. This runs automatically in CI — PRs with new failures will not pass

### When Analyzing Errors
1. **CHECK** `./hive-mind/troubleshooting/` for known issues
2. **MATCH** error messages against documented symptoms
3. **APPLY** documented solutions before attempting new fixes

### When Solving New Problems
1. **DOCUMENT** the solution in `./hive-mind/troubleshooting/` if it's a bug fix
2. **DOCUMENT** the pattern in `./hive-mind/patterns/` if it's reusable architecture
3. **UPDATE** the relevant README index files

---

## Session Architecture

Demo builds use a three-phase flow. The demo-starter is a **component library with worked examples**, not a fixed template to tweak. Demos span a complexity spectrum from config-only to design-from-scratch.

### Session 1: Planning
- Coaching conversation (Opening -> Ideation/Discovery -> Strategy -> UX Design)
- **`/opsx:propose`**: creates OpenSpec proposal (replaces DEMO_PLAN.md), auto-inventories the component library, produces gap analysis in design.md, creates capability specs, and derives tasks
- Bridge tasks to beads: `./scripts/openspec-to-beads.sh <change-name> --epic <epic-id>`
- **Strongly recommend ending the session here** for context headroom

### Session 2+: Build
- Agent reads OpenSpec specs as PRIMARY input (not beads checklists)
- Reads `design.md` gap analysis to understand: Reuse / Modify / Build New / Not Needed
- Runs `bd ready` to pick next unblocked task
- For each task: implements against spec scenarios, verifies via browser, marks complete
- Generates `demoTracks.ts` from golden path specs (agent reads spec metadata, writes TypeScript)
- Child agents (via Task tool) can work on independent tasks in parallel

### UAT Pass
- **`/opsx:verify`**: runs golden path end-to-end browser tests + design review
- Produces structured pass/fail report with screenshot evidence
- Auto-fixes minor issues (prompt wording, config), flags scope changes for SA review
- Can be a separate session or final phase of build session

### Why This Matters
Splitting sessions keeps each phase focused. OpenSpec preserves the qualitative UX vision from coaching as formal specs that the build agent must satisfy — preventing the "change the index and colors" shortcut.

---

## Spec-Driven Development with OpenSpec

OpenSpec adds a specification layer that preserves qualitative UX vision from coaching as formal, verifiable requirements.

### How It Works

| Artifact | Purpose | Location |
|----------|---------|----------|
| `proposal.md` | Coaching output: persona, wow moments, journey, capabilities (replaces DEMO_PLAN.md) | `openspec/changes/<name>/` |
| `design.md` | Auto-inventory gap analysis: Reuse / Modify / Build New / Not Needed | `openspec/changes/<name>/` |
| `specs/<capability>/spec.md` | Qualitative experience requirements with GIVEN/WHEN/THEN scenarios | `openspec/changes/<name>/specs/` |
| `tasks.md` | Implementation checklist derived from gap analysis (not generic templates) | `openspec/changes/<name>/` |
| `verify-report.md` | UAT results with pass/fail per scenario and screenshot evidence | `openspec/changes/<name>/` |

### Role Separation

| Layer | Tool | Owns |
|-------|------|------|
| **What the experience must be** | OpenSpec specs | Qualitative requirements, design decisions, golden path scenarios |
| **Tracking execution status** | Beads | Issue status, dependencies, progress, close reasons |

### Cursor Slash Commands

```
/opsx:explore   — Think through ideas, investigate the codebase (read-only)
/opsx:propose   — Coaching output + auto-inventory + gap analysis + specs + tasks
/opsx:apply     — Implement tasks against spec scenarios
/opsx:verify    — UAT golden path tests + design review (post-build)
/opsx:archive   — Archive completed change, merge specs into living docs
```

### Spec Templates

Reusable templates in `openspec/templates/specs/` — copy and fill placeholders per demo:

| Template | Purpose | Required? |
|----------|---------|-----------|
| `demo-experience` | Quality contract: domain authenticity, production feel, no template artifacts | Always |
| `search-page` | Search config, facets, result display, empty states | If search UI needed |
| `custom-page` | Domain-specific page: layout, interactions, content, imagery | Per custom page |
| `agent-persona` | Chat identity, domain knowledge, conversation flow | Per agent |
| `branding` | Brand extraction, theme, cross-page consistency | If customer branding |
| `golden-paths` | End-to-end UAT scenarios + demoTracks.ts generation source | Always |
| `data-architecture` | Multi-index, multi-agent, custom backend routes | If complex architecture |

### Gap Analysis in design.md

The `/opsx:propose` command auto-inventories the component library (reads `docs/COMPONENT_REGISTRY.md`, scans pages/hooks/routes) and produces a gap analysis:

- **Reuse** — config-only changes (point to different index, set brand colours)
- **Modify** — extend existing components (add badge to SearchResultCard)
- **Build New** — components/pages/agents that don't exist in the template
- **Not Needed** — template features to hide from this demo

This makes effort distribution visible and prevents config-only work on complex demos.

### Golden Paths and Demo Guide Generation

Golden path specs serve two purposes:
1. **UAT test scenarios** — verified by `/opsx:verify`
2. **demoTracks.ts source** — the build agent reads structured metadata (Navigation, Steps, Talking Points) to generate the demo guide

Each scenario includes: `**Navigation:**` (becomes a demo pill), `**Steps:**` (becomes steps[]), `**Talking points:**` (becomes talkingPoints[]), `**Expected outcome:**` (UAT only, not in demo guide).

### Bridge to Beads

```bash
./scripts/openspec-to-beads.sh <change-name> --dry-run    # Preview
./scripts/openspec-to-beads.sh <change-name> --epic <id>   # Create issues
```

Beads tasks are lightweight: they reference spec files for acceptance criteria instead of embedding 15 checkboxes.

---

## Pattern & Component Discovery

### BEFORE WRITING ANY NEW CODE
1. **Read `docs/COMPONENT_REGISTRY.md`** — know what frontend/backend components exist and their maturity
2. **Read the relevant `hive-mind/patterns/{category}/README.md`** — know what patterns apply
3. Only THEN propose new code. Reuse existing components and patterns.

### Pattern Categories (55+ patterns in hive-mind)

| Category | Directory | Use When |
|----------|-----------|----------|
| **Agent Builder** | `hive-mind/patterns/agent-builder/` | Agent Builder, A2A, MCP, streaming, userscript overlay |
| **Search** | `hive-mind/patterns/search/` | Retrievers, indexing, ESQL, inference, query rules, LTR |
| **Observability** | `hive-mind/patterns/observability/` | OTel, browser SDK, ESQL analytics, personalization |
| **Open Crawler** | `hive-mind/patterns/open-crawler/` | Crawler configs, extraction, Elasticsearch integration |
| **Agent Frameworks** | `hive-mind/patterns/agent-frameworks/` | Agno coordinator setup, multi-agent with memory |
| **Data Generation** | `hive-mind/patterns/data/` | Datasets, generators, LLM data creation, fidelity requirements |
| **Branding** | `hive-mind/patterns/branding/` | Extracting brand themes from websites, component theming |
| **EUI** | `hive-mind/patterns/eui/` | EUI + Vite or Next.js setup, SSR workarounds |
| **E-Commerce** | `hive-mind/patterns/ecommerce/` | Cart tracking, demo datasets, OTel attribution |
| **Deployment** | `hive-mind/patterns/deployment/` | Cloud Run, Docker, dynamic ports, dev scripts |

> **Full index**: `hive-mind/patterns/README.md` lists all 55+ patterns with descriptions.

---

## Project Stack

- **Frontend**: Vite + React 18 + EUI 110 + TypeScript
- **Backend**: Python FastAPI
- **Styling**: EUI components + Tailwind CSS (where EUI doesn't cover)

### EUI-Specific Rules

1. **Icons**: All EUI icons must be registered in `frontend/src/iconCache.ts`.
   - The `npm run dev` script now auto-generates this cache on start.
   - If you add a new icon while the server is running, you must restart the server or run `npm run generate-icons`.
   - **GUARANTEE**: If an icon is missing, the app will not crash but the icon will not render. Always verify icons exist in the cache.
2. **Theme**: Use EUI theme variables, support light/dark modes. See `hive-mind/patterns/eui/DEMO_PAGE_VISUAL_DESIGN.md` for CSS variable reference.
3. **Colors for EuiAvatar**: Must use hex values, not CSS variables

---

## Visual Quality Standards

> These rules apply whenever you build or modify UI pages. The goal is to produce demo-quality output on the first pass, not after multiple rounds of human review.

### During Page Construction

**Before writing any page code**, read:
- `docs/PAGE_RECIPES.md` — pick the closest recipe for your page type
- `docs/DEMO_PAGE_VISUAL_DESIGN.md` — CSS variables, typography scale, spacing system, image strategy
- `docs/COMPONENT_REGISTRY.md` — know what components exist (especially `HeroSection`, `FeatureGrid`, `PhotoStrip`, `BrandedEmptyState`)

**Build sequence**: visual scaffold first (hero + sections + images), then wire data, then polish. Never build logic-first and add visuals later.

1. **Dark mode first**: Use CSS variables (`var(--euiTextColor)`, `var(--euiColorLightShade)`, etc.) for all text, backgrounds, and borders. Never hardcode hex colours for theme-dependent surfaces. See `docs/DEMO_PAGE_VISUAL_DESIGN.md`.
2. **Imagery over text**: Every custom page must include at least 3 domain-relevant visual elements — hero banners, card thumbnails with images, photo strips, stat ribbons, or colored badges. Text-only pages feel like wireframes. Use `unsplash()` from `utils/images.ts` with `STOCK_IMAGES` categories (14 domains available), and `loading="lazy"` on all images. Use `getStockCategory(domain)` to find the best image category.
3. **Use `FeatureGrid` for card layouts**: Instead of manually composing `EuiFlexGroup` + `EuiCard` for every page, use the `FeatureGrid` component for responsive card grids with images and click actions.
4. **Empty states matter**: Empty lists, grids, and accordions should use `BrandedEmptyState` with a visual element (image, icon, or photo strip) and actionable text. Never leave bare "no data" text.
5. **Brand the chat**: If the page has a chat interface, give the assistant a custom name, avatar, and personalised greeting that references the demo persona. Don't use the default sparkles icon.
6. **Fixed header awareness**: The app header is `position: fixed` at 56px height. Any content below it needs explicit offset. Don't rely on EUI generating spacer divs — use `position: fixed` with calculated `top` values for full-viewport layouts.

### Visual Verification (MANDATORY)

**After building or significantly modifying any page, you MUST visually verify it before marking the work as complete.**

**Reference docs** (read before building pages):
- `docs/PAGE_RECIPES.md` — standard layout patterns and visual checklist
- `docs/DEMO_PAGE_VISUAL_DESIGN.md` — CSS variables, typography, spacing, dark mode rules

If browser tools are available (Playwright MCP or Claude-in-Chrome):
1. Navigate to the page in the browser
2. Take a screenshot and review it — check for: hidden content, broken layout, missing images, dark mode issues
3. Verify minimum visual elements: hero/header present, at least 3 images or visual elements per page, no text-only wireframe sections
4. If the page has interactive sections (accordions, toggles, scrolling), test those and screenshot the results
5. Toggle dark/light mode and verify both render correctly

If browser tools are NOT available:
1. Run `npx tsc --noEmit` to verify TypeScript compiles
2. Check the browser console for errors via `./dev logs-snapshot`
3. Note in your completion message that visual verification was not performed and should be checked manually

**Do not mark a UI task as complete without visual verification.** "It compiles" is not "it looks right."

### Branding Verification (MANDATORY when custom brand exists)

**After creating or modifying a brand theme, you MUST run the branding check:**
```bash
./dev verify-template --check branding
```
This catches broken logo URLs, external URLs blocked by CDNs, missing DEMO_TITLE, stale
"Elastic Demo Starter" titles, and incomplete brand color fields. **Do not mark branding
complete if this check reports failures.** External logo URLs are flagged as warnings because
CDNs frequently block automated requests — always download logos locally.

---

## Branding System

This project supports multiple brand themes with two approaches:

### Option 1: Brand Editor (Manual)
- Available at `/brands` in the running app
- Simple UI for setting colors and uploading logos
- Brands stored in `backend/data/brands.json`
- Good for quick demos with basic color customization

### Option 2: AI-Powered Extraction (Advanced)
- Use vibe coding to extract branding from websites
- Creates theme files in `frontend/src/branding/[brandName]Theme.ts`
- Can extract fonts, gradients, and complex styling
- See `hive-mind/patterns/branding/BRANDING_EXTRACTION_PATTERNS.md`

### Key Files
- `frontend/src/branding/index.ts` - Brand registry and types
- `frontend/src/branding/BrandContext.tsx` - React context for theming
- `backend/app/routes/branding.py` - REST API for brand CRUD
- **Template**: Use `exampleTheme.ts` as the template for AI-extracted brands

### Browser Tools (Playwright MCP Auto-Configuration)

Branding extraction requires browser tools. `setup.sh` automatically configures Playwright MCP for Claude Code users:

- **What it does**: During setup (step 6/6), detects if `@playwright/mcp` is available via npx and creates/updates `.mcp.json` with the Playwright MCP server configuration.
- **`.mcp.json` is gitignored** — it's environment-specific and auto-generated per machine.
- **If already configured**: Setup skips this step (checks for existing `"playwright"` entry).
- **If npx is unavailable or the package can't be resolved**: Setup prints a warning with install instructions.
- **Manual configuration**: Add this to `.mcp.json` in the project root:
  ```json
  {
    "mcpServers": {
      "playwright": {
        "command": "npx",
        "args": ["@playwright/mcp@latest"]
      }
    }
  }
  ```
- **Cursor users**: No configuration needed — Cursor has a built-in browser.

### Testing Themes (Local Development)
For themes you don't want committed to the repo:
- Prefix the filename with `testing`: `testingGovukTheme.ts`, `testingAcmeTheme.ts`
- These files are gitignored but auto-loaded for local development
- The "testing" prefix is stripped from the brand ID (`testingGovuk` → `govuk`)
- Use `?brand=govuk` or localStorage to activate

---

## Dev Commands

```bash
./dev start            # Start both servers (background)
./dev stop             # Stop servers
./dev status           # Check if running
./dev verify           # Quick setup verification (checks .env, venv, health)
./dev verify-template  # Structural integrity checks (routes, contracts, builds)
./dev test-agent       # Test Agent Builder connection (sends test message)
./dev logs-snapshot    # View recent logs (NON-BLOCKING - use this!)
./dev logs             # Follow logs (BLOCKS FOREVER - don't use in scripts)
./dev open             # Open browser
./setup.sh             # Reconfigure Elastic connection
```

> ⚠️ **AI Agents**: Always use `./dev logs-snapshot` instead of `./dev logs`.
> The `logs` command uses `tail -f` which hangs indefinitely.
> Use `./dev logs-snapshot 100` to see the last 100 lines.

### Localhost URL Check

Hardcoded `http://localhost` URLs in frontend source break Cloud Run deployments. A CI check and standalone script catch regressions:

```bash
./scripts/check-localhost-urls.sh   # Run locally (exit 0 = clean, exit 1 = violations)
```

Exceptions (overlay userscripts, OverlayGuidePage, vite.config.ts) are excluded. To add a new exception, edit the grep exclusions in the script.

### Port Discovery (for AI Agents)

Ports are **dynamic** - don't assume defaults! Multiple demos may run on different ports.

```bash
./dev status                      # Shows actual running ports
cat .dev-pids/backend.port        # Backend port (e.g., 8001, 8002, ...)
cat .dev-pids/frontend.port       # Frontend port (e.g., 3000, 3001, ...)
```

See `hive-mind/patterns/deployment/DYNAMIC_PORT_CONFIGURATION.md` for details.

---

## Cloud Run Deployment

This project can be deployed to Google Cloud Run with IAP (Identity-Aware Proxy) protection.

> 🔒 **SECURITY: Demos must ALWAYS be behind IAP authentication.**
> Never deploy demos with public access (`--allow-unauthenticated` or `ingress=all`).
> IAP ensures only authorized users (@elastic.co) can access the demo.
> See `docs/DEPLOYMENT.md` for IAP setup instructions.

> ⚠️ **IMPORTANT: Always use SIDECARS for Cloud Run deployment.**
> The all-in-one approach (Dockerfile.cloudrun) has reliability issues with supervisor.
> The sidecar approach is battle-tested and works correctly.

> 💡 **CRITICAL IAP GOTCHA**: Cloud Run needs `allUsers` as invoker even with IAP!
> This is counter-intuitive but required. IAP authenticates at the Load Balancer,
> then the LB calls Cloud Run. Without `allUsers` invoker, you get 403 Forbidden
> even after successful IAP authentication. This is secure because `ingress:
> internal-and-cloud-load-balancing` blocks direct access - all traffic must
> go through the IAP-protected Load Balancer. The deploy script now adds this
> automatically. See `hive-mind/patterns/deployment/CLOUDRUN_SIDECAR_DEPLOYMENT.md`.

### Quick Deploy (Sidecars - RECOMMENDED)

```bash
# Set your credentials
export ELASTICSEARCH_URL="https://your-cluster.es.cloud.com"
export ELASTIC_API_KEY="your-api-key"
export SERVICE_NAME="my-demo"
export BASE_PATH="/my-demo/"

# Deploy with sidecars - THIS IS THE ONLY RECOMMENDED APPROACH
./deploy/deploy-cloudrun.sh
```

### Deployment Options

| Option | Command | Status |
|--------|---------|--------|
| **Sidecars** | `./deploy/deploy-cloudrun.sh` | ✅ **USE THIS** |
| ~~All-in-One~~ | ~~`cloudbuild.yaml`~~ | ⚠️ Not recommended - supervisor issues |
| **Debug** | `Dockerfile.cloudrun.simple` | For troubleshooting FastAPI only |

### Key Files

```
deploy/                          # Deployment configurations
├── Dockerfile.nginx             # Frontend container
├── Dockerfile.fastapi           # Backend container
├── Dockerfile.otel-collector    # OTel Collector
├── nginx.conf                   # Nginx routing config
├── service.yaml                 # Cloud Run service definition
└── deploy-cloudrun.sh           # Main deployment script
Dockerfile.cloudrun              # All-in-one image
Dockerfile.cloudrun.simple       # Debug image (FastAPI only)
cloudbuild.yaml                  # Cloud Build (all-in-one)
cloudbuild-sidecar.yaml          # Cloud Build (sidecars)
```

See `docs/DEPLOYMENT.md` for full guide.

---

## Environment Variables & Secrets

This project uses a tiered approach to environment variables and secrets.

### Tiers

| Tier | Location | Purpose | Gitignored |
|------|----------|---------|------------|
| **App config** | `backend/.env` | Read-only API key, service URLs, ports, feature flags | Yes |
| **Admin secrets** | `.secrets/ootb-admin.env` | Write/admin API keys for indexing, testing, data loading | Yes |
| **Deployment** | Root `.env` | Cloud Run-specific overrides (GCP project, region, etc.) | Yes |

### Key Principles

1. **`backend/.env` is for the running app** — it should only contain a **read-only** API key with search permissions. This is what `setup.sh` / `interactive_setup.py` writes.
2. **`.secrets/.env` is for development and testing** — admin API keys with write/index permissions, credentials for data ingestion scripts, and any other secrets that shouldn't be in the app `.env`.
3. **Never commit secrets** — both `.env` and `.secrets/` are gitignored. The `.env.example` files document the expected variables without values.
4. **Scripts should check both locations** — ingestion and data loading scripts should load from `.secrets/.env` first (admin key), falling back to `backend/.env` (read-only key).

### `.secrets/` Directory Structure

```
.secrets/
└── ootb-admin.env    # OOTB serverless cluster credentials (admin + readonly keys)
```

The secrets file uses these variable names:
```bash
ELASTICSEARCH_URL=...       # Cluster URL
KIBANA_URL=...              # Kibana URL
ADMIN_API_KEY=...           # Full-access key for indexing, data loading, testing
READONLY_API_KEY=...        # Read-only key (same value as ELASTIC_API_KEY in backend/.env)
```

> **Current state**: `backend/.env` has `ELASTIC_API_KEY` set to the read-only key.
> Ingestion scripts that need write access must load `ADMIN_API_KEY` from `.secrets/ootb-admin.env`.

### How Credentials Are Loaded

| Component | Library | Loads from | Notes |
|-----------|---------|------------|-------|
| **FastAPI app** | `python-decouple` | `backend/.env` | AutoConfig searches `backend/` directory only |
| **Ingestion scripts** (`scripts/`) | `python-dotenv` | `load_dotenv(override=True)` | Loads nearest `.env` — set vars before running or use `--api-key` flag |
| **Generators** (`backend/scripts/`) | `os.getenv()` | Environment only | Must `export` or use `dotenv` in calling script |
| **Crawler scripts** | `os.getenv()` | Environment only | Accept `--api-key` CLI flag as override |

### For AI Agents: Loading Credentials in Scripts

When writing new scripts that need Elasticsearch **write** access:

```python
# Standard pattern for scripts that need admin/write access
import os
from pathlib import Path

from dotenv import load_dotenv

# Find project root (adjust parents[N] for script depth)
project_root = Path(__file__).resolve().parents[N]

# Load app .env first (base config), then secrets (override with admin key)
load_dotenv(project_root / 'backend' / '.env')
secrets_env = project_root / '.secrets' / 'ootb-admin.env'
if secrets_env.exists():
    load_dotenv(secrets_env, override=True)

es_url = os.getenv('ELASTICSEARCH_URL')
api_key = os.getenv('ADMIN_API_KEY') or os.getenv('ELASTIC_API_KEY')
```

For **read-only** scripts (search, queries), just load `backend/.env` — no secrets needed.

### Inference Endpoints

Inference endpoint IDs (e.g. `.elser-2-elastic`, `.jina-embeddings-v3`) **change frequently** on Elastic Serverless. Never hardcode them in documentation or index mappings.

- Use `<YOUR_INFERENCE_ENDPOINT>` as a placeholder in patterns and docs
- Check the live cluster: `GET /_inference` to discover current endpoint IDs
- The project defaults to Jina embeddings via Elastic Inference Service (EIS)
- See `backend/scripts/load_serverless_ootb.py` for the canonical inference setup

---

## Agent Builder & Workflows (Programmatic Management)

**IMPORTANT: Always create agents, tools, and workflows via the API — not the Kibana UI.**

Coding agents should never tell the user to "go to Kibana" to create an agent. Everything can be scripted.

### Full API References (in hive-mind)

- **Agent & Tool CRUD**: `hive-mind/patterns/agent-builder/AGENT_BUILDER_API_MANAGEMENT.md`
- **Workflow YAML & API**: `hive-mind/patterns/agent-builder/WORKFLOW_INTEGRATION.md`
- **MCP Endpoint**: `hive-mind/patterns/agent-builder/MCP_SERVER_INTEGRATION.md`

### Backend Proxy Routes

The backend provides proxy routes that keep API keys secure. Use these instead of hitting Kibana directly:

```bash
# Agent CRUD
GET    /api/agent/agents                  # List all agents
GET    /api/agent/agents/{id}             # Get agent config + prompt
POST   /api/agent/agents                  # Create agent
PUT    /api/agent/agents/{id}             # Update agent
DELETE /api/agent/agents/{id}             # Delete agent

# Tool CRUD
GET    /api/agent/tools                   # List all tools
POST   /api/agent/tools                   # Create tool (index_search, esql, workflow)
DELETE /api/agent/tools/{id}              # Delete tool

# Chat
POST   /api/agent/chat                    # Streaming SSE (uses AGENT_ID from .env)
POST   /api/agent/chat/test               # Non-streaming test (accepts any agent_id)

# Workflows (full CRUD already exists)
POST   /api/workflows                     # Create workflow (body: { yaml: "..." })
POST   /api/workflows/{id}/run            # Run workflow
GET    /api/workflows/executions/{id}     # Check execution status
```

### Agent Setup Sequence

1. **Create tools first** — `POST /api/agent/tools` for each data index
2. **Create the agent** — `POST /api/agent/agents` with system prompt and tool IDs
3. **Test via API** — `POST /api/agent/chat/test` with representative messages
4. **Iterate** — `PUT /api/agent/agents/{id}` to refine the prompt
5. **Set AGENT_ID** in `backend/.env` — the streaming chat UI uses this
6. **Test via UI** — `./dev test-agent`

---

## Issue Tracking with Beads (if `.beads/` exists)

This project uses **beads (bd)** as its persistent issue tracker. Beads survive session restarts, context compaction, and agent handoffs — unlike in-memory task lists which are lost when a session ends.

**Check if enabled**: Look for `.beads/` folder in project root.

**Rule**: Any work that takes more than a few minutes should have a bead. Temporary, in-session task lists (for example, an editor's built-in task features) are fine for within-session coordination, but beads are the source of truth across sessions.

> **Full reference**: `hive-mind/meta/workflows/BEADS_ISSUE_TRACKER.md`

### Setup (once per project)

```bash
# Install Claude Code hooks for automatic context recovery
bd setup claude --project
```

This adds SessionStart and PreCompact hooks that inject `bd prime` context automatically.

### Session Start (ALWAYS do this)

```bash
bd ready                    # What can I work on? (no blockers)
bd list --status in_progress  # Active work from previous sessions?
bd blocked                  # What's stuck and why
bd stats                    # Overview of project state
```

### Before Working on an Issue

```bash
bd show <id>                # Read description AND acceptance criteria
bd update <id> --status in_progress
bd comment <id> "Starting work on this"
```

**If the issue has no acceptance criteria, ask the user before starting.**

### During Work

```bash
bd comment <id> "Progress: implemented X, working on Y"

# Found a bug while working? Create it and link back:
bd create "Bug: null check missing" --type bug --deps "discovered-from:<id>"

# Hit a blocker? Record it:
# Syntax: bd dep add <blocked-issue> <blocker-issue>
# Reads as: "<blocked> depends on <blocker>"
bd dep add <id> <blocker-id>
```

### Completing Work — Write Rich Close Reasons

Close reasons are how future sessions recover context. Include: what was done, key files, decisions, remaining work.

**Bad**: `bd close <id> -r "Done"`
**Good**: `bd close <id> -r "Implemented X in path/to/file.py. Key decision: used approach Y. Remaining: edge case Z needs testing."`

```bash
bd comment <id> "Done — <brief summary of what was done>"
bd close <id> -r "What was done, key files changed, any remaining issues"
bd ready                    # Check what unblocked
```

### Git Commit Integration

Always reference issues in commits:
```bash
git commit -m "[<id>] description of change"
```

### Creating Issues

```bash
bd create "title" \
  --type [bug|feature|task|epic|chore] \
  --priority [0-4] \           # 0=critical, 2=normal(default), 4=backlog
  --acceptance "- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Tests pass"
```

### Agent Teams + Beads

When using Claude Code agent teams, beads and internal tasks serve different roles:
- **Beads** = persistent backlog (what needs doing across sessions)
- **TaskCreate/TaskList** = ephemeral session plan (how agents divide work right now)

Workflow: pick beads issues → create TaskCreate items for each agent → agents work in parallel → close beads issues when done.

### Quick Reference

```bash
bd ready                         # Unblocked work
bd blocked                       # Stuck items
bd show <id>                     # Full details + acceptance criteria
bd update <id> --status in_progress  # Claim it
bd comment <id> "message"        # Progress note
bd close <id> -r "reason"        # Done (always use -r, not --comment)
bd list --status open            # All open
bd list --type bug --priority 0  # Critical bugs
bd search "keyword"              # Search issues
```

### Dependencies — Getting It Right

```bash
# ⚠️ bd dep add uses POSITIONAL args, NOT the blocks: prefix syntax
# The blocks: prefix ONLY works with --deps during bd create

# Syntax: bd dep add <blocked-issue> <blocker-issue>
# Meaning: first arg DEPENDS ON second arg (second blocks first)

# Example: "auth" must be done before "dashboard" can start
bd dep add dashboard-id auth-id  # dashboard depends on auth

# Example: creating with deps inline (blocks: prefix works HERE)
bd create "Build dashboard" --deps "blocks:auth-id"

# Verify the relationship
bd dep tree <id>                 # Shows what blocks this issue
bd blocked                       # Shows all blocked issues and why
```





## hive-mind-start
# Hive Mind

This project uses hive-mind for Elastic integration patterns and AI skills.

## Pattern-First Workflow
1. Before implementing, check `hive-mind/.hive-mind-index.json` for relevant patterns by tag.
2. Read the full pattern file before coding.
3. Follow established conventions and code structure.
4. Check skill `references/` directories for troubleshooting docs.

## Skills Routing
Route tasks through domain skills in `hive-mind/skills/`:
- Agent chat, MCP, orchestration -> hive-agent-builder
- Team beads conventions -> hive-beads
- Brand extraction, theming -> hive-demo-branding
- Dataset registry, generation -> hive-demo-data
- Composite demo guides -> hive-demo-recipes
- Docker, Cloud Run, dev scripts -> hive-deployment
- Cart tracking, e-commerce -> hive-ecommerce
- EUI, Vite, Next.js, theming -> hive-eui-frontend
- MCP server configs -> hive-mcp
- AI personas, prompts -> hive-meta
- Open Crawler setup -> hive-open-crawler
- OpenTelemetry, tracing, analytics -> hive-otel-tracing
- SA coaching, demo ideation, hackathon brainstorming -> hive-sa-coaching
- Retrievers, indexing, query templates -> hive-search-retrievers

## Recipe Shortcuts
- /hive-demo-recipes search -> recipes/SEARCH_DEMO.md
- /hive-demo-recipes agent-builder -> recipes/AGENT_BUILDER_DEMO.md
- /hive-demo-recipes ecommerce -> recipes/ECOMMERCE_DEMO.md

## Discovery Commands
- /hive-mind list -> python hive-mind/scripts/hive-mind-index-cli.py list
- /hive-mind search <tag> -> python hive-mind/scripts/hive-mind-index-cli.py search <tag>
- /hive-mind tags [prefix] -> python hive-mind/scripts/hive-mind-index-cli.py tags [prefix]

Start with `hive-mind/skills/hive-mind/SKILL.md` for broad requests.
## hive-mind-end
