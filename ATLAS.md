# Atlas — Agent Memory on Elasticsearch

A self-contained demo showing how Elasticsearch can be the **unified cognitive
layer** for any AI agent. Atlas is a personal assistant whose entire memory —
episodic events, semantic facts, procedural playbooks — lives in Elasticsearch.
Every chat turn streams a hybrid recall (BM25 + Jina v5 dense) before grounding
its reply.

The same memory layer is exposed as an **MCP server** so external agents
(Claude Desktop, Cursor, custom LangGraph) can plug in unchanged.

## What it demonstrates

| Feature | How |
|---|---|
| **Three memory types** | Three indices: `atlas_memory_episodic`, `atlas_memory_semantic`, `atlas_memory_procedural` |
| **Auto-embedding** | `semantic_text` fields with `inference_id: .jina-embeddings-v5-text-small` (no client-side calls) |
| **Hybrid recall** | RRF retriever fusing BM25 + `semantic` query (Jina v5 dense vectors) |
| **LLM via EIS** | `.anthropic-claude-4.6-opus-chat_completion` (no provider API key) |
| **Consolidation** | Single Claude pass distills episodic events into deduped semantic facts AND updates procedural playbooks (success/failure counts, refined steps, new playbooks) |
| **Conflict resolution** | Agent detects when new information contradicts a recalled fact, forgets the old doc, and writes the corrected one — automatically, in-turn |
| **Multi-tenant isolation** | DLS API keys per user (or app-level `term: user_id` filter as fallback when the cluster's parent key is org-managed) |
| **External agents** | Native MCP server at `/api/atlas/mcp/{user_id}` — paste-ready Claude Desktop config |
| **Bring your own data** | Federate over a shared `atlas_catalog` index (or any customer index) via `include_catalog: true` |

## Architecture

```
┌─── Frontend (React + EUI) ───┐
│ /atlas split layout:         │
│   chat (left)                │
│   memory inspector (right):  │
│     - Semantic / Episodic /  │
│       Procedural tabs        │
│     - "consolidate" button   │
│     - recalled-doc badges    │
│   user switcher (sarah/james/priya) │
└──────────────┬───────────────┘
               │ SSE
┌──── Backend (FastAPI) ───────┐
│  /api/atlas/chat   — agent loop  │
│  /api/memory/*     — write/recall/consolidate/forget/list  │
│  /api/atlas/mcp/*  — MCP JSON-RPC for external agents  │
│  app/atlas/agent.py     — Claude loop with tools  │
│  app/atlas/consolidate  — episodic → semantic + procedural  │
│  app/atlas/memory/  — schema + ops + DLS client cache  │
└──────────────┬───────────────┘
               │
┌──── Elastic Cloud Serverless ────┐
│  Three memory indices            │
│  Shared atlas_catalog            │
│  EIS endpoints (no ML nodes):    │
│    .jina-embeddings-v5-text-small│
│    .anthropic-claude-4.6-opus    │
└──────────────────────────────────┘
```

## Setup

```bash
# 1. Configure your project (Elastic Cloud Serverless Search project)
#    Edit backend/.env:
#      ELASTICSEARCH_URL=https://<project>.es.<region>.gcp.elastic.cloud:443
#      KIBANA_URL=https://<project>.kb.<region>.gcp.elastic.cloud/
#      ELASTIC_API_KEY=<project-scoped admin key from Kibana > API Keys>

# 2. Initialize indices and seed deep narratives for all 3 users
cd backend
uv run python -m scripts.atlas.deep_narratives   # generate narratives via Claude (cached, ~10 min first run)
uv run python -m scripts.atlas.reset_and_seed    # drop + recreate indices, bulk-seed sarah/james/priya
uv run python -m scripts.atlas.seed_catalog      # seeds 11 docs (Lumio knowledge base)
uv run python -m scripts.atlas.bootstrap_users   # mints DLS keys (skipped gracefully if cluster rejects)

# 3. Run the dev servers
cd ..
./dev start

# 4. Open the demo
open http://localhost:3000/atlas
```

> **Quick re-seed (after first run):** `deep_narratives` caches to `backend/data/atlas_seed/`. Subsequent resets just run `reset_and_seed` — no EIS spend.

## Demo script

1. **Cold recall.** As `sarah`, ask: _"My hub keeps disconnecting again."_ Inspector shows `recall_memory` firing — returns Sarah's 3 connectivity episodes AND the firmware 3.1.4 known-issue doc from the catalog.
2. **Grounded reply.** Agent: _"Since your Hub v2 was reset in March and the drops came back, this is the firmware 3.1.4 Zigbee regression — the fix is in 3.2.0, released last week."_ No generic troubleshooting tree — the answer is grounded in her history and catalog.
3. **New fact written.** Say: _"I also have a Lumio Range Extender I never set up."_ Agent writes a new semantic fact (green in inspector), visible immediately in the Semantic tab.
4. **Cross-session recall.** Click **Clear**, then ask: _"What do you know about my setup?"_ Memory persists — agent lists Hub v2, 3 motion sensors, doorbell, 2 smart bulbs, and the Range Extender from step 3.
5. **Consolidation — semantic.** Click **consolidate** in the inspector — Claude distills events 1, 3, 4 (three distinct connectivity-drop reports) into a single deduped semantic fact with `source_episodes` provenance.
6. **Consolidation — procedural.** Still as sarah, walk through the Zigbee troubleshooting playbook steps and end with _"ok that fixed it"_. Click **consolidate** again. The `troubleshoot_zigbee_connectivity` playbook's `success_count` increments (visible as `✓ 1` in the Procedural tab). A novel multi-step fix the agent hasn't seen before will create a new playbook at confidence ≥ 0.8.
7. **Conflict resolution.** Say _"Actually I moved — we left Bristol and now live in Edinburgh."_ The agent recalls the Bristol fact, calls `forget_memory` on the old doc, then writes the Edinburgh fact. Click **Clear** and ask _"Where do I live?"_ — only Edinburgh is returned.
8. **Tenant isolation.** Switch dropdown to `james`. Ask: _"Where am I based and what devices do I have?"_ Agent: _"You're based in Amsterdam and own a Hub v1."_ Zero leakage of Sarah's Hub v2/connectivity history.
9. **Bring your own data.** As james, ask: _"Why are my smart bulbs only showing white?"_ Agent federates over James's personal memory (Hub v1) AND catalog (bulb compatibility doc): _"Lumio Smart Bulbs require Hub v2 with firmware 3.2.0 for full color — your Hub v1 supports white only."_
10. **Power-user depth.** Switch to `priya`. Ask: _"Why is the kitchen sensor only active at night?"_ Agent recalls that Priya disabled daytime triggers because her dog Clio jumps on the counter after crows. That detail was mentioned once, casually, months ago.

## Connecting external agents via MCP

The Atlas backend is a fully compliant MCP server. Any Claude client can connect to it and use `recall_memory`, `write_memory`, and `forget_memory` as native tools over the existing Elasticsearch indices.

### Available tools

| Tool | What it does |
|---|---|
| `recall_memory(query, memory_types?, k?, include_catalog?)` | Hybrid BM25 + Jina v5 search, returns top-10 hits across all three memory indices |
| `write_memory(memory_type, text, fact_type?, confidence?)` | Write a new semantic fact or procedural playbook |
| `forget_memory(memory_id, memory_type)` | Delete a specific memory by ID |

---

### Connecting Claude Desktop (step-by-step)

**Prerequisites**

- The dev backend must be running: `./dev start` (verify with `./dev status`)
- Node.js must be installed (check: `node --version`) — needed for `npx mcp-remote`

**Step 1 — get the actual backend port**

```bash
cat .dev-pids/backend.port
# e.g. 8001
```

**Step 2 — open the Claude Desktop config file**

```bash
open "~/Library/Application Support/Claude/"
# then open claude_desktop_config.json in any editor
# If the file doesn't exist yet, create it
```

Or open directly:
```bash
open -a TextEdit "~/Library/Application Support/Claude/claude_desktop_config.json"
```

**Step 3 — add the Atlas MCP servers**

Paste the following, replacing `8001` with the port from Step 1 if different. If the file already has other `mcpServers`, merge the Atlas entries in — don't overwrite.

```json
{
  "mcpServers": {
    "atlas-memory-sarah": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8001/api/atlas/mcp/sarah"]
    },
    "atlas-memory-james": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8001/api/atlas/mcp/james"]
    },
    "atlas-memory-priya": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8001/api/atlas/mcp/priya"]
    }
  }
}
```

**Step 4 — fully quit and relaunch Claude Desktop**

> ⚠️ Closing the window is not enough — Claude Desktop only reads MCP config at startup.

On Mac: **Cmd+Q** (or Claude menu → Quit Claude), then reopen from Applications or Spotlight.

**Step 5 — verify the connection**

Open a new Claude Desktop conversation. You should see a tools/hammer icon in the input bar. Click it to confirm the three `atlas-memory-*` tools appear.

Then try:

```
Use atlas-memory-sarah to tell me about Sarah's ongoing hub connectivity issue.
```

Claude will call `recall_memory` and ground its reply in the Elasticsearch indices. You'll see the tool call appear in the conversation.

---

### Auto-generated config snippet

The backend generates ready-to-paste config per user (useful if you only want one user connected):

```bash
curl http://localhost:8001/api/atlas/mcp/sarah/info | python3 -m json.tool
```

Returns `client_config.mcpServers` ready to copy into the Claude Desktop config file.

---

### Connecting Claude Code (`.mcp.json`)

The project `.mcp.json` already contains all three Atlas entries. Claude Code picks it up automatically. If tools don't appear, type `/mcp` in the Claude Code prompt to force a reload.

---

### No auth (dev mode)

The MCP endpoint has no authentication in this build. User isolation is enforced by the `user_id` path parameter and the `term: user_id` Elasticsearch filter. In production, add a bearer-token check in `backend/app/atlas/routes/mcp.py` before the `get_user_client` call.

---

## Testing the architecture at depth

The default seed ships ~6 episodic + ~6 semantic + 1 procedural per user — useful for first-glance demos but not enough to prove that hybrid recall actually finds the right memory once a user has a year of accumulated history.

The depth harness adds a third persona (`priya`, an architect in Bengaluru), regenerates ~200 episodic + ~60 semantic + ~4 procedural items per user via Claude (cached to `backend/data/atlas_seed/`), interleaves ~20 hand-authored ground-truth needles with surprising specifics (a dog named Whiskey, a houseboat in Sixhaven, a tulip-pollen allergy), and then runs a paraphrased-query eval that reports Recall@1/5/10, MRR, and a tenant-isolation sweep.

```bash
cd backend
# 1. generate narratives once (cached on disk, ~$5-10 EIS spend, ~10 min)
uv run python -m scripts.atlas.deep_narratives

# 2. drop + recreate the memory indices, then bulk-seed all personas
uv run python -m scripts.atlas.reset_and_seed

# 3. run the retrieval-quality eval (QA-style passage retrieval)
uv run python -m scripts.atlas.eval_recall
# -> backend/data/atlas_eval/qa_report-<ts>.md  (human-readable summary)
# -> backend/data/atlas_eval/qa_report-<ts>.json (raw per-query results)
```

Pass criteria the eval enforces:

- **Recall@10 ≥ 0.85** across all (question, doc) pairs
- **Recall@5 ≥ 0.75**
- **Cross-tenant leakage = 0** (eval exits non-zero if any doc owned by user A surfaces when querying as user B)

Once the eval passes, three demo beats exercise depth in the live UI (`./dev start`, then `/atlas`):

- **Long-range temporal recall.** As `sarah`, ask: _"Remember the bedroom sensor issue last spring?"_ → agent must surface the April-2025 sunrise-reflection incident from a haystack of ~250 unrelated memories.
- **Incidental-mention recall.** As `sarah`, ask: _"What did I tell you about Whiskey?"_ → agent must surface the cable-chewing constraint and the 2.1m sensor-mounting fact, neither of which was the topic of the original conversation.
- **Isolation under depth.** Switch to `priya` and ask the same Whiskey question → agent must answer with no recalled memories. (Priya's actual dog is named Clio.)

## Files of interest

```
backend/app/atlas/                    ← all Atlas backend logic lives here
├── agent.py            # Multi-turn tool-using loop; XML-structured system prompt; conflict resolution
├── consolidate.py      # Episodic → semantic facts + procedural updates (single LLM pass)
├── llm.py              # EIS chat_completion streaming client
├── tools.py            # Tool schemas + dispatch (recall k=10 default)
├── memory/             # Elasticsearch schema, ops, DLS
│   ├── constants.py    # Index names + EIS endpoint IDs
│   ├── operations.py   # write/recall/list/forget/update_procedural + RRF retriever
│   ├── user_keys.py    # DLS-scoped client cache
│   └── mappings/*.json # Index schemas (semantic_text + Jina v5)
└── routes/             # HTTP endpoints
    ├── chat.py         # POST /api/atlas/chat (SSE)
    ├── mcp.py          # POST /api/atlas/mcp/{user_id} (JSON-RPC)
    └── memory.py       # /api/memory/{write,recall,consolidate,forget,list}

backend/scripts/atlas/               ← all Atlas setup scripts live here
├── init_memory.py      # Idempotent index creation + endpoint check
├── seed_memories.py    # Per-user sample memories (small, hand-authored)
├── seed_catalog.py     # Shared catalog seed
├── bootstrap_users.py  # Per-user DLS API keys (graceful fallback)
├── needles.py          # Hand-authored ground-truth needles + paraphrased queries (used by eval)
├── deep_narratives.py  # Generates rich multi-month narratives per user via Claude (cached on disk)
├── bulk_seed.py        # helpers.bulk indexer for narratives + needles (semantic_text auto-embeds)
├── reset_and_seed.py   # Drops + recreates memory indices, then bulk-seeds all personas
└── eval_recall.py      # Recall@k / MRR + tenant-isolation sweep, writes report markdown

frontend/src/atlas/                  ← all Atlas frontend code lives here
├── AtlasMemoryPage.tsx # Demo page (chat + inspector layout)
├── MemoryInspector.tsx # Live memory tabs (Semantic/Episodic/Procedural)
├── useAtlasChat.ts     # SSE streaming chat state hook
└── api.ts              # Memory REST + chat SSE client
```

## Adapting for a customer

| Change | Where |
|---|---|
| Persona / system prompt | `backend/app/atlas/agent.py` → `SYSTEM_PROMPT` |
| Different LLM | `backend/app/atlas/memory/constants.py` → `LLM_INFERENCE_ID` |
| Different embedding model | same file → `EMBEDDING_INFERENCE_ID`; update mappings' `inference_id` |
| Customer's existing catalog | point `include_catalog` to their actual index by editing `recall_memory(..., include_catalog=...)` to pass through any index name; or set `INDEX_CATALOG = "<customer-index>"` |
| Pre-seed user data | `backend/scripts/atlas/seed_memories.py` |

## Limits in this build

- DLS API key minting requires a project-scoped admin key. The cloud-managed
  org-level "Unrestricted API Key" rejects derived sub-keys with explicit
  privileges; the bootstrap script falls back gracefully and the application
  layer's `term: user_id` filter still enforces isolation.
- The `forget_memory` tool deletes one document; rolling-window deletion
  (e.g., 90-day ILM) is not configured because Serverless manages ILM
  automatically.
- LangGraph checkpointer adapter (Phase 10 in the plan) is out of scope —
  the Anthropic-via-EIS chat loop here doesn't need it.
