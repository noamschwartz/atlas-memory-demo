# Feature Catalog

> **Quick reference for building your demo.** Pick the building blocks you need, skip what you don't.
>
> Each feature has a 1-line description → link to full docs. Progressive disclosure.

______________________________________________________________________

## How to Use This Catalog

1. **Describe your demo goal** to your AI assistant (or read through yourself)
2. **Pick building blocks** from the tables below
3. **Follow the links** for detailed setup of only what you need
4. **Skip everything else** — most demos use 3-5 features, not all 15+

______________________________________________________________________

## Delivery Method

*How will users access your demo?*

| Feature | Description | When to Use | Details |
|---------|-------------|-------------|---------|
| **Full Demo App** | Complete web app with pages, navigation, branding | Standalone demo you host and present | [PAGES.md](./PAGES.md) |
| **Overlay Chat** | Inject floating chat onto *any* website via browser extension | Demo on customer's live site without code changes | [Overlay Pattern][overlay-pattern] |
| **Embeddable Widget** | React component to embed in existing apps | Customer wants to integrate into their app | [FloatingChatWidget](./CUSTOMIZATION.md#floatingchatwidget) |

______________________________________________________________________

## AI Capabilities

*What AI-powered features do you need?*

| Feature | Description | Requires | Details |
|---------|-------------|----------|---------|
| **Agent Chat** | Streaming chat with reasoning & tool calls | Kibana URL + API Key + Agent ID | [Agent Builder Integration][agent-integration] |
| **Multi-Agent (A2A)** | Coordinate multiple specialist agents via LLM router | Agent Builder + LLM Proxy | [A2A Coordinator Pattern][a2a-pattern] |
| **MCP Tools** | Browse & test Model Context Protocol tools | Agent with MCP configured | [MCP Server Integration][mcp-pattern] |
| **Workflows** | Chain ES queries, AI calls, and connectors into automated procedures | ES 9.3+ with Workflows enabled | [Workflow Integration][workflow-pattern] |
| **Conversation Audit** | Review agent reasoning, tool calls, full history | Agent Builder connection | [Audit Page](./PAGES.md#audit-page) |

______________________________________________________________________

## Search & Discovery

*Does your demo involve searching content or products?*

| Feature | Description | Requires | Details |
|---------|-------------|----------|---------|
| **Full-Text Search** | Search UI with results, pagination | ES URL + API Key + Index | [Search Page](./PAGES.md#search-page) |
| **Faceted Filtering** | Category, brand, price filters | ES index with keyword fields | `frontend/src/config/searchConfig.ts` |
| **Hybrid/Semantic Search** | Combine BM25 + vector search | ES + embeddings model | [Retriever Builder Pattern][retriever-pattern] |
| **Query Rules** | Curated results, synonyms, promotions | ES query rules configured | [Query Rules + Retrievers][query-rules] |

______________________________________________________________________

## Observability

*Do you want to track performance or user behaviour?*

| Feature | Description | Requires | Details |
|---------|-------------|----------|---------|
| **Backend APM** | Trace API latency, ES queries, agent calls | APM endpoint + headers | [OTel Python FastAPI][otel-python] |
| **Browser Tracing** | Frontend spans, user journey tracking | APM endpoint | [Browser OTel SDK][browser-otel] |
| **Search Analytics** | Click-through rate, zero-results, top queries | ES index for events | [ES|QL Search Analytics][esql-analytics] |
| **Personalisation Tracking** | User preferences, A/B test events | OTel + ES | [Personalisation Tracking][otel-personalisation] |

______________________________________________________________________

## Presentation & Branding

*How should your demo look?*

| Feature | Description | Requires | Details |
|---------|-------------|----------|---------|
| **Custom Branding** | Colors, logos, fonts matching customer | Nothing (optional) | [BRANDING.md](./BRANDING.md) |
| **AI Brand Extraction** | Auto-extract branding from any website | Firecrawl MCP (optional) | [Branding Extraction Pattern][branding-extraction] |
| **Brand Editor UI** | Visual editor for non-technical users | Nothing | [Brand Editor Page](./PAGES.md#brand-editor-page) |
| **Demo Guide** | Presenter notes, talking points, flow | Nothing | [DEMO_GUIDE_TEMPLATE.md](./DEMO_GUIDE_TEMPLATE.md) |
| **Dark/Light Mode** | Theme toggle, accessible colors | Built-in | Automatic with EUI |

______________________________________________________________________

## Common Combinations

*Not sure what you need? Here are typical demo setups:*

### "Show AI on customer's website"
→ **Overlay Chat** + **Agent Chat** + **Custom Branding**

### "Product search demo"  
→ **Full Demo App** + **Full-Text Search** + **Faceted Filtering** + **Custom Branding**

### "AI assistant with search grounding"
→ **Full Demo App** + **Agent Chat** + **Full-Text Search** + **Conversation Audit**

### "Multi-agent orchestration"
→ **Full Demo App** + **Multi-Agent (A2A)** + **Conversation Audit**

### "AI assistant with operational automation"
→ **Full Demo App** + **Agent Chat** + **Workflows** + **Custom Branding**

### "Performance-focused demo"
→ Any of the above + **Backend APM** + **Search Analytics**

______________________________________________________________________

## Dependency Quick Reference

| If you want... | You need in `.env`... |
|----------------|----------------------|
| Agent Chat | `KIBANA_URL`, `ELASTIC_API_KEY`, `AGENT_ID` |
| Multi-Agent | Above + `LLM_PROXY_URL`, `LLM_PROXY_API_KEY` |
| Search | `ELASTICSEARCH_URL` or `ELASTIC_CLOUD_ID`, `ELASTIC_API_KEY`, `SEARCH_INDEX` |
| APM/OTel | `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS` |
| Branding | Nothing required (fully optional) |
| Workflows | `WORKFLOWS_API_KEY`, `WORKFLOWS_KIBANA_URL` (separate key with `workflowsManagement` privilege) |

______________________________________________________________________

## Next Steps

1. **Quick setup**: Run `./setup.sh` then start a new AI session
2. **Page reference**: [PAGES.md](./PAGES.md)
3. **Customisation**: [CUSTOMIZATION.md](./CUSTOMIZATION.md)

______________________________________________________________________

<!-- Link references for cleaner tables -->
[overlay-pattern]: ../hive-mind/patterns/agent-builder/USERSCRIPT_INJECTION_PATTERN.md
[agent-integration]: ../hive-mind/patterns/agent-builder/AGENT_BUILDER_INTEGRATION.md
[a2a-pattern]: ../hive-mind/patterns/agent-builder/A2A_COORDINATOR_PATTERN.md
[mcp-pattern]: ../hive-mind/patterns/agent-builder/MCP_SERVER_INTEGRATION.md
[retriever-pattern]: ../hive-mind/patterns/search/RETRIEVER_BUILDER_PATTERN.md
[query-rules]: ../hive-mind/patterns/search/QUERY_RULES_RETRIEVERS.md
[otel-python]: ../hive-mind/patterns/observability/OTEL_PYTHON_FASTAPI_SETUP.md
[browser-otel]: ../hive-mind/patterns/observability/BROWSER_OTEL_SDK.md
[esql-analytics]: ../hive-mind/patterns/observability/ESQL_SEARCH_ANALYTICS.md
[otel-personalisation]: ../hive-mind/patterns/observability/OTEL_PERSONALIZATION_TRACKING.md
[branding-extraction]: ../hive-mind/patterns/branding/BRANDING_EXTRACTION_PATTERNS.md
[workflow-pattern]: ../hive-mind/patterns/agent-builder/WORKFLOW_INTEGRATION.md
