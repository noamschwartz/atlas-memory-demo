# Use Case Registry

> **Purpose**: Track validated use cases with real customer examples and available datasets.  
> **Status**: Living document - update as we validate new use cases.  
> **Last Updated**: 2026-01-26

---

## Validation Criteria

A use case is considered **validated** when it has:

| Criteria | Required | Description |
|----------|----------|-------------|
| ✅ Working demo | Yes | End-to-end demo that runs without errors |
| ✅ Customer example | Yes | At least one real customer engagement |
| ✅ Dataset available | Yes | Tested dataset documented in DEMO_DATASETS.md |
| 📝 Pattern documented | Recommended | Hive Mind pattern for reuse |
| 🎨 Branding tested | Recommended | Successfully applied customer branding |

---

## Validated Use Cases

### ✅ E-commerce Product Search

| Attribute | Details |
|-----------|---------|
| **Status** | Validated |
| **Customer Examples** | [Add customer names/codes here] |
| **Datasets** | Open Food Facts (grocery), Icecat (electronics) |
| **Demo Type** | Full demo starter |
| **Key Features** | Faceted search, product cards, images, RetrieverBuilder |
| **Pattern** | `hive-mind/patterns/ecommerce/README.md` |

**What it demonstrates:**
- Full-text search with relevance tuning
- Category/brand/price facets
- Product images and details
- Hybrid search (BM25 + semantic)

---

### ✅ AI Chat Assistant (Agent Builder)

| Attribute | Details |
|-----------|---------|
| **Status** | Validated |
| **Customer Examples** | [Add customer names/codes here] |
| **Datasets** | Any indexed content |
| **Demo Type** | Full demo starter |
| **Key Features** | SSE streaming, reasoning display, tool calls |
| **Pattern** | `hive-mind/patterns/agent-builder/AGENT_BUILDER_INTEGRATION.md` |

**What it demonstrates:**
- Conversational AI with context
- Streaming responses
- Agent reasoning visibility
- Tool call visualisation

---

### ✅ Multi-Agent Orchestration (A2A)

| Attribute | Details |
|-----------|---------|
| **Status** | Validated |
| **Customer Examples** | [Add customer names/codes here] |
| **Datasets** | Multiple domain datasets |
| **Demo Type** | Full demo starter |
| **Key Features** | LLM coordinator, agent routing, unified UI |
| **Pattern** | `hive-mind/patterns/agent-builder/A2A_COORDINATOR_PATTERN.md` |

**What it demonstrates:**
- Multiple specialised agents
- Intent-based routing
- Coordinated responses
- Complex workflow handling

---

### ✅ Workflow Automation (Elastic Workflows)

| Attribute | Details |
|-----------|---------|
| **Status** | Validated |
| **Customer Examples** | [Add customer names/codes here] |
| **Datasets** | Any indexed content + domain-specific workflow recipes |
| **Demo Type** | Full demo starter |
| **Key Features** | YAML workflow recipes, one-click escalation, execution polling, recipe library |
| **Pattern** | `hive-mind/patterns/agent-builder/WORKFLOW_INTEGRATION.md` |

**What it demonstrates:**
- Automated operational procedures triggered from search results
- Chaining ES queries, AI agent calls, and connectors in YAML
- One-click escalation with real-time status feedback
- Recipe library for non-technical users to deploy automation
- Bridge from "find the answer" to "take action" — all inside Elastic

---

## In Progress

### 🔄 Recipe/Shopping Cart Assistant

| Attribute | Details |
|-----------|---------|
| **Status** | In Progress |
| **Customer Examples** | Foodland (reference: alan-visser/foodland-chatbot) |
| **Datasets** | Recipe datasets (TBD), grocery products |
| **Demo Type** | Overlay chat pattern |
| **Key Features** | Cart-aware recommendations, recipe suggestions, streaming |
| **Pattern** | `hive-mind/patterns/agent-builder/USERSCRIPT_INJECTION_PATTERN.md` |
| **Implementation** | `frontend/src/scripts/overlay-chat.user.js` |
| **Beads** | elastic-agent-starter-hb3, elastic-agent-starter-5o2 |

**What it demonstrates:**
- Cart event tracking
- Contextual recommendations
- Cross-sell/upsell patterns
- RAG with shopping context

**Gaps to close:**
- [ ] Need tested recipe dataset documented
- [x] ~~Need streaming support in overlay~~ — Implemented in `overlay-chat.user.js` (uses `responseType: 'stream'`)
- [ ] Need second customer validation

---

### 🔄 Fraud Detection Analytics

| Attribute | Details |
|-----------|---------|
| **Status** | In Progress |
| **Customer Examples** | [TBD] |
| **Datasets** | [TBD - need fraud/transaction dataset] |
| **Demo Type** | Full demo starter |
| **Key Features** | Anomaly detection, alerting, dashboards |
| **Pattern** | TBD |

**Gaps to close:**
- [ ] Need sample fraud dataset
- [ ] Need ES|QL dashboard patterns
- [ ] Need customer validation

---

## Planned

### 📋 Documentation/Support Assistant

| Attribute | Details |
|-----------|---------|
| **Status** | Planned |
| **Customer Examples** | None yet |
| **Datasets** | Crawled documentation sites |
| **Demo Type** | Overlay or full demo |
| **Key Features** | Doc search, contextual help, code examples |

**To validate:**
- [ ] Crawl a public docs site
- [ ] Test overlay on docs site
- [ ] Validate with customer

---

### 📋 B2B Product Catalogue

| Attribute | Details |
|-----------|---------|
| **Status** | Planned |
| **Customer Examples** | None yet |
| **Datasets** | [Need industrial/B2B dataset] |
| **Demo Type** | Full demo starter |
| **Key Features** | Spec-heavy search, part numbers, compatibility |

**To validate:**
- [ ] Find suitable B2B dataset
- [ ] Build search with technical specs
- [ ] Validate with customer

---

### 📋 Security/SIEM Analytics

| Attribute | Details |
|-----------|---------|
| **Status** | Planned |
| **Customer Examples** | None yet |
| **Datasets** | [Need security event dataset] |
| **Demo Type** | Full demo starter |
| **Key Features** | Event correlation, threat detection, dashboards |

**To validate:**
- [ ] Source security event dataset
- [ ] Build ES|QL dashboards
- [ ] Validate with customer

---

## Dataset Requirements by Use Case

| Use Case | Dataset Needs | Available | Gap |
|----------|---------------|-----------|-----|
| Workflow Automation | Domain data + YAML recipes | ✅ Any indexed content | None |
| E-commerce Search | Products with images, prices, categories | ✅ Open Food Facts, Icecat | None |
| Recipe Assistant | Recipes with ingredients, instructions | 🔄 Partial | Need curated set |
| Fraud Detection | Transactions with fraud labels | ❌ | Need dataset |
| Documentation | Crawled docs with sections | 🔄 Use crawler | Need example |
| B2B Catalogue | Industrial products with specs | ❌ | Need dataset |
| Security/SIEM | Security events, logs | ❌ | Need dataset |

---

## How to Validate a New Use Case

1. **Build the demo** using demo starter or overlay pattern
2. **Test with real-ish data** - use or create appropriate dataset
3. **Run with a customer** - even a friendly internal stakeholder counts
4. **Document what worked** - update this registry
5. **Note gaps and issues** - create beads for follow-up
6. **Share in #demo-starter** - help others learn

---

## Contributing

When you validate a new use case:

1. Add it to the appropriate section above
2. Fill in all the attributes
3. Link to relevant patterns and datasets
4. Create beads for any gaps identified
5. Share your learnings in Slack

---

*This document is the source of truth for what we can confidently demo.*
