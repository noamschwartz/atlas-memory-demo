# Demo Guide: [Your Demo Name]

> **Instructions**: Copy this file to `DEMO_GUIDE.md` and fill in the sections below.
> Delete this instruction block when done.

______________________________________________________________________

## Overview

**Demo Name**: [e.g., "Acme Retail Assistant"]\
**Target Audience**: [e.g., "Retail customers wanting to find products and track orders"]\
**Primary Use Case**: [e.g., "Product search with AI-assisted recommendations"]

### What This Demo Shows

<!-- List the key capabilities this demo highlights. See docs/FEATURE_CATALOG.md for all options. -->

**Delivery Method:**
- [ ] Full Demo App (standalone web app)
- [ ] Overlay Chat (injected onto customer's website)
- [ ] Embeddable Widget (FloatingChatWidget component)

**Features:**
- [ ] Agent Builder chat with streaming responses
- [ ] Multi-agent orchestration (A2A)
- [ ] Custom branding
- [ ] Search with facets
- [ ] APM/Observability tracking
- [ ] [Add your own...]

______________________________________________________________________

## Quick Start

```bash
# Clone and setup
git clone [your-repo-url]
cd [repo-name]
./setup.sh

# Start the demo
./dev start
./dev open
```

**Demo URL**: <http://localhost:3000>

______________________________________________________________________

## Demo Flow

<!-- Describe the recommended path through the demo for presentations -->

### 1. Landing Page (/)

**What to show**: [Describe what's on the landing page and what to highlight]

**Talking points**:

- Point 1
- Point 2

### 2. Chat Page (/chat)

**What to show**: [Describe the chat interaction to demonstrate]

**Sample prompts to try**:

```text
"[Your first demo prompt]"
"[Your second demo prompt]"
"[Your third demo prompt]"
```

**Talking points**:

- How the agent reasons through the request
- Tool calls being made
- Response quality

### 3. [Additional Pages...]

<!-- Add sections for each page you want to include in the demo flow -->

### Overlay Demo (if using injection approach)

<!-- If your demo uses the overlay chat on a customer's website -->

**Target Website**: [URL where overlay is injected]

**Setup**:
1. Install Tampermonkey browser extension
2. Load the userscript from `frontend/src/scripts/overlay-chat.user.js`
3. Configure `@match` pattern for target URL
4. Set `backendUrl` to your running demo backend

**What to show**:
- [Describe the customer site and where chat appears]
- [Key interactions to demonstrate]

**Talking points**:
- "This is running on [customer]'s actual website"
- "No code changes required on their end"
- "The chat connects securely to our backend"

______________________________________________________________________

## Configuration

### Environment Variables

| Variable             | Purpose                  | Where to Get It                      |
| -------------------- | ------------------------ | ------------------------------------ |
| `KIBANA_URL`         | Agent Builder connection | Elastic Cloud console                |
| `ELASTIC_API_KEY`    | Authentication           | Kibana → Stack Management → API Keys |
| `AGENT_ID`           | Which agent to use       | Agent Builder → Your Agent → URL     |
| [Add custom vars...] |                          |                                      |

### Agent Setup

**Agent Name**: [Name of the Agent Builder agent]\
**Agent ID**: [The agent ID used]

**Agent Capabilities**:

- [List what the agent can do]
- [e.g., "Search product catalog"]
- [e.g., "Check inventory levels"]

**Connected Data Sources**:

- [e.g., "Elasticsearch index: products"]
- [e.g., "API connector: inventory-service"]

______________________________________________________________________

## Branding

**Brand**: [Brand name used]\
**Theme File**: `frontend/src/branding/[brand]Theme.ts`

**Colors**:

- Primary: `#XXXXXX`
- Accent: `#XXXXXX`

**Logo Location**: [Path to logo file or URL]

______________________________________________________________________

## Troubleshooting

### Common Issues

| Symptom                       | Cause                      | Fix                                       |
| ----------------------------- | -------------------------- | ----------------------------------------- |
| "Agent not connected"         | Missing or invalid API key | Re-run `./setup.sh` and enter credentials |
| [Add demo-specific issues...] |                            |                                           |

### Getting Help

- Check `./dev logs-snapshot` for error details
- Review `hive-mind/troubleshooting/` for known issues
- [Add your support channel...]

______________________________________________________________________

## Architecture

```text
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│    Backend      │────▶│  Agent Builder  │
│  (React + EUI)  │     │   (FastAPI)     │     │    (Kibana)     │
│   :3000         │     │   :8001         │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Elasticsearch  │
                        │   (Optional)    │
                        └─────────────────┘
```

______________________________________________________________________

## Customizations Made

<!-- Document any changes from the base template -->

### Frontend Changes

- [e.g., "Added custom ProductCard component"]
- [e.g., "Modified chat greeting message"]

### Backend Changes

- [e.g., "Added /api/inventory endpoint"]

### Agent Changes

- [e.g., "Added product search tool"]
- [e.g., "Connected to inventory database"]

______________________________________________________________________

## Files Reference

| File                                    | Purpose                   |
| --------------------------------------- | ------------------------- |
| `frontend/src/pages/ChatPage.tsx`       | Main chat interface       |
| `frontend/src/branding/[brand]Theme.ts` | Brand theme definition    |
| `backend/.env`                          | Environment configuration |
| [Add demo-specific files...]            |                           |

______________________________________________________________________

## Presenter Notes

<!-- Optional: Notes for anyone presenting this demo -->

### Before the Demo

- [ ] Verify `./dev status` shows both servers running
- [ ] Test the chat with a sample prompt
- [ ] Clear browser cache if switching brands
- [ ] [Add your checklist items...]

### During the Demo

- [Timing notes, transitions, etc.]

### Q&A Preparation

- **Q**: [Anticipated question]
- **A**: [Prepared answer]

______________________________________________________________________

*Last updated: [Date]*\
*Demo version: [Version or commit hash]*
