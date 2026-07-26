# Atlas — Agent Memory on Elasticsearch

A research demo showing how Elasticsearch can be the **unified cognitive layer** for any AI agent. Three synthetic users (Sarah, James, Priya) each carry months of episodic history, semantic facts, and procedural playbooks, all in Elasticsearch. The agent recalls and writes memory on every turn. The same memory layer is exposed as an **MCP server** so Claude Code, Claude Desktop, Cursor, or any other MCP client can plug straight in.

| | |
|---|---|
| **Memory types** | Episodic, Semantic, Procedural |
| **Recall** | Hybrid BM25 + Jina v5 dense via RRF |
| **LLM** | Claude via Elastic Inference Service (no provider API key) |
| **External agents** | MCP server at `/api/atlas/mcp/{user_id}` |

**→ See [ATLAS.md](./ATLAS.md) for the full setup guide, demo script, and MCP connection instructions.**

---

## Quick Start

You should be running in 1–3 minutes once you have your Elastic credentials in hand.

### Prerequisites

- [**uv**](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [**Node.js 18+**](https://nodejs.org/)
- An **Elasticsearch cluster + Kibana** (Elastic Cloud or self-hosted): cluster URL, Kibana URL, and an API key with read/write permissions
- **Elastic Inference Service** enabled on the project, with a Jina v5 embedding endpoint and a Claude chat-completion endpoint. The seed script will name any missing endpoint in its error output.

### Five steps

```bash
# 1. Clone
git clone https://github.com/noamschwartz/atlas-memory-demo.git
cd atlas-memory-demo

# 2. Configure: edit backend/.env and set ELASTICSEARCH_URL, ELASTIC_API_KEY, KIBANA_URL
cp backend/.env.example backend/.env

# 3. Install dependencies, verify the cluster, and start both servers
./setup.sh

# 4. Seed the memory indices and the shared product catalog
cd backend
uv run python -m scripts.atlas.reset_and_seed
uv run python -m scripts.atlas.seed_catalog
cd ..

# 5. Open the demo
open http://localhost:3000/atlas
```

> `./setup.sh` starts the backend and frontend for you. If you stop them later (`./dev stop`), restart with `./dev start`.

> If port `3000` or `8001` is already in use, `./dev` picks the next free port and writes it to `.dev-pids/frontend.port` / `.dev-pids/backend.port`. Check those files (or the URLs printed at the end of `./setup.sh`) and open that port instead.

> The `ELASTIC_API_KEY` in `backend/.env` is the read-only key used by the running app. Admin / ingestion scripts that need write access read a separate `ADMIN_API_KEY` from `.secrets/ootb-admin.env` (gitignored). See `backend/.env.example` for the annotated template.

### What you'll see

Three synthetic users with months of memory, an agent that recalls relevant entries on every turn via hybrid BM25 + dense search, and an inline memory inspector that shows exactly which documents were retrieved and written.

---

## Architecture

```
Frontend (Vite + React + EUI)  ↔  Backend (FastAPI)  ↔  Elastic Stack
         :3000                           :8001               (ES + Kibana + EIS)
```

---

## Running the Demo

```bash
./dev start            # Start backend + frontend in background
./dev stop             # Stop both servers
./dev status           # Check running ports and health
./dev logs-snapshot    # View recent logs (non-blocking)
./dev test-agent       # Test Agent Builder connectivity
./dev open             # Open browser
```

Both servers auto-reload on code changes.

---

## Features

- **Three memory types**: Episodic (events + timestamps), Semantic (facts + preferences), Procedural (playbooks + how-tos)
- **Hybrid recall**: BM25 + Jina v5 dense via RRF, robust to paraphrased queries
- **Server-side embeddings**: `semantic_text` with Elastic Inference Service, no separate embedding API key
- **Per-user isolation**: `term: user_id` filter, with optional DLS API keys
- **MCP server**: `/api/atlas/mcp/{user_id}`, ready for Claude Desktop, Cursor, or any MCP agent

---

## Configuration

All configuration lives in `backend/.env` (copy from `backend/.env.example`).

| Variable | Required | Description |
|---|---|---|
| `ELASTICSEARCH_URL` | Yes | Elastic Cloud or self-hosted cluster URL |
| `ELASTIC_API_KEY` | Yes | API key with read/write access |
| `KIBANA_URL` | Yes | Kibana URL (same workspace) |
| `PORT` | No | Backend port (default `8001`) |

See `backend/.env.example` for the fully annotated template, including optional OTel and feature flags.

---

## Deployment

Deploy to Google Cloud Run with sidecars (frontend, FastAPI, OTel collector). See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for the full guide, including IAP setup.

```bash
export ELASTICSEARCH_URL="https://your-cluster.es.cloud.es.io"
export ELASTIC_API_KEY="your-api-key"
export SERVICE_NAME="atlas-memory-demo"
export BASE_PATH="/atlas/"
./deploy/deploy-cloudrun.sh
```

> **Security**: always deploy behind IAP. Never use `--allow-unauthenticated`.

---

## MCP Integration

Endpoint: `http://localhost:8001/api/atlas/mcp/{user_id}`. Tools: `recall_memory`, `write_memory`, `forget_memory`. See [ATLAS.md](./ATLAS.md#mcp-integration) for Claude Desktop and Cursor connection snippets.

---

## Project Structure

```
backend/
├── app/
│   ├── atlas/          # Atlas memory system (agent, tools, memory ops, routes)
│   ├── routes/         # Search, chat, branding, analytics, A2A, MCP endpoints
│   └── main.py         # FastAPI entry point
├── scripts/atlas/      # Seeding scripts (reset_and_seed, bootstrap_users, etc.)
└── data/
    ├── profiles.json   # User profile definitions
    └── atlas_seed/     # Cached Claude-generated narratives (speeds up seeding)

frontend/src/
├── pages/              # 17 pages (Atlas, Chat, Search, Geo, Branding, etc.)
├── components/         # 49 reusable components
└── config/             # Demo configuration (prompts, personas, tracks)
```

---

## License

[MIT](./LICENSE) © 2026 Noam Schwartz.
