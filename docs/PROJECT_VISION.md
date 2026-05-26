# Elastic Demo Starter: Project Vision & Goals

> **Last Updated**: 2026-01-26  
> **Status**: Active Development

## Executive Summary

The **Elastic Demo Starter** is an internal tool for Elastic employees to rapidly build customised customer demos. It provides verified architectural patterns, secure deployment models, and AI-assisted workflows that eliminate common pitfalls and accelerate demo creation from weeks to hours.

**Important**: Demos built with this starter are designed to be **shown to customers**, not to become production code. They embed best practices (secure Cloud Run deployment, proper API key handling, IAP authentication) so that what customers see reflects how we'd recommend building for real.

---

## Vision

**Enable Elastic employees to build compelling, professional customer demos in hours, not weeks.**

We achieve this by:
1. **Golden master codebase** — Correct patterns and secure defaults built-in
2. **AI-assisted development** — "Vibe coding" with Cursor/Claude for rapid customisation
3. **Shared knowledge base** — Hive Mind patterns that grow with each demo
4. **Demo tracking** — Branch-based workflow to track usage and learn from each engagement

---

## Target Audience

| Role | How They Use This |
|------|-------------------|
| **Solution Architects** | Build tailored demos for customer engagements |
| **Customer Architects** | Prototype solutions using customer branding/data |
| **Consultants** | Showcase Elastic capabilities in workshops |
| **Sales Engineers** | Quick demos with minimal setup time |
| **Partners** | (Secondary) Build solutions on Elastic with guidance |

> **Not for**: Customers building production applications. Point them to official Elastic documentation and examples instead.

---

## Objectives & Key Results (OKRs)

### Objective 1: Accelerate Demo Creation

| Key Result | Target | Current Status |
|------------|--------|----------------|
| Time to first working demo | < 30 minutes | ✅ Achieved (with vibe coding) |
| Lines of code written manually | < 50 for basic customisation | ✅ Achieved |
| Number of demo types supported | 6+ | ✅ 6 (Search, Chat, Analytics, A2A, Fraud, Observability) |

### Objective 2: Eliminate Common Failure Modes

| Key Result | Target | Current Status |
|------------|--------|----------------|
| SSE streaming issues | Zero | ✅ Solved (proxy pattern documented) |
| EUI icon cache errors | Zero | ✅ Solved (auto-generation) |
| API authentication failures | Clear error messages | ✅ Implemented |
| CORS issues | Zero for standard deployments | ✅ Solved |

### Objective 3: Build Reusable Knowledge

| Key Result | Target | Current Status |
|------------|--------|----------------|
| Documented patterns in Hive Mind | 30+ | ✅ 35+ patterns |
| Troubleshooting guides | 10+ | ✅ 10 guides |
| Tested demo datasets | 5+ domains | 🔄 In progress (2 verified) |

### Objective 4: Support Diverse Use Cases

| Key Result | Target | Current Status |
|------------|--------|----------------|
| E-commerce search demos | Full support | ✅ Complete |
| AI chat/assistant demos | Full support | ✅ Complete |
| Multi-agent orchestration | Full support | ✅ Complete |
| Analytics dashboards | Full support | ✅ Complete |
| Fraud detection demos | Pattern available | 🔄 In progress |
| Observability demos | OTel integration | ✅ Complete |

---

## Current Status

### What's Working ✅

- **Search Experiences**: Full-text search, faceted filtering, RetrieverBuilder patterns
- **AI Chat**: Agent Builder integration with SSE streaming, reasoning display, tool visualisation
- **Multi-Agent (A2A)**: LLM coordinator pattern for orchestrating multiple agents
- **Branding**: AI-powered brand extraction, multi-theme support, brand editor UI
- **Analytics**: ES|QL dashboards, search analytics (CTR, MRR, zero-results)
- **Deployment**: Docker, Cloud Run (sidecar pattern), IAP authentication
- **Developer Experience**: Setup wizard, preflight checks, hot-reload, AI context files

### In Progress 🔄

- **Dataset Library**: Compiling tested datasets for diverse demo domains
- **Fraud Analytics**: Complete demo flow for anomaly detection
- **Recipe/Recommendation Demos**: Shopping cart → recipe suggestion pattern

### Planned 📋

- **Visual Demo Builder**: Low-code interface for demo configuration
- **Demo Gallery**: Showcase of completed demos for inspiration
- **Performance Benchmarks**: Latency and scalability metrics

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Demo Starter                                    │
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│  │    Frontend     │     │     Backend     │     │   Hive Mind         │   │
│  │  Vite + React   │────▶│    FastAPI      │     │   (Knowledge Base)  │   │
│  │  + EUI + TS     │     │    + Python     │     │   - Patterns        │   │
│  │                 │     │                 │     │   - Troubleshooting │   │
│  │  Features:      │     │  Features:      │     │   - Workflows       │   │
│  │  - Chat UI      │     │  - Agent Proxy  │     │                     │   │
│  │  - Search UI    │     │  - Search API   │     └─────────────────────┘   │
│  │  - Analytics    │     │  - Analytics    │                               │
│  │  - Branding     │     │  - OTel         │                               │
│  └─────────────────┘     └─────────────────┘                               │
│           │                       │                                         │
└───────────┼───────────────────────┼─────────────────────────────────────────┘
            │                       │
            ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Elastic Stack                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Elasticsearch   │  │ Agent Builder   │  │ APM Server      │              │
│  │ - Data storage  │  │ - LLM agents    │  │ - Traces        │              │
│  │ - Search        │  │ - Tool calls    │  │ - Metrics       │              │
│  │ - Analytics     │  │ - RAG           │  │                 │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Demo Type Coverage

### Fully Supported

| Demo Type | Description | Key Components |
|-----------|-------------|----------------|
| 🔍 **E-commerce Search** | Product search with facets, images | RetrieverBuilder, faceted UI |
| 💬 **AI Chat Assistant** | Conversational AI with tools | Agent Builder, SSE streaming |
| 🔗 **Multi-Agent (A2A)** | Orchestrated agent workflows | LLM coordinator, agent routing |
| 📊 **Search Analytics** | CTR, MRR, zero-results analysis | OTel, ES\|QL dashboards |
| 📈 **Business Analytics** | ES\|QL powered dashboards | Custom visualisations |
| 🎨 **Brand Customisation** | White-label demos | Theme extraction, CSS variables |

### In Development

| Demo Type | Description | Status |
|-----------|-------------|--------|
| 🛡️ **Fraud Detection** | Anomaly detection, alerting | Pattern available |
| 🛒 **Shopping Assistant** | Cart-aware recommendations | Pattern documented |
| 🔐 **Security Analytics** | SIEM-style dashboards | Planned |

### Built-In Best Practices

Every demo automatically includes production-quality patterns that customers can reference:

| Best Practice | Implementation | Why It Matters |
|---------------|----------------|----------------|
| **Secure deployment** | Cloud Run + IAP authentication | Shows secure-by-default approach |
| **API key handling** | Backend proxy, never in frontend | Demonstrates credential hygiene |
| **Observability** | OTel instrumentation built-in | Shows our own stack in action |
| **Error handling** | Clear messages, graceful degradation | Professional presentation |
| **Responsive UI** | EUI components, mobile-friendly | Works on any screen |

> **Philosophy**: What we demo should reflect how we'd recommend customers build. Cutting corners in demos teaches bad habits.

---

## Demo Workflow & Tracking

### Recommended Workflow

```bash
# 1. Clone the starter
git clone https://github.com/elastic/elastic-demo-starter.git acme-retail-demo
cd acme-retail-demo

# 2. Setup creates a local demo branch (not pushed)
./setup.sh
# Prompts: "Demo name?" → creates local branch: demos/acme-retail-2026-01

# 3. Work on the demo
# ... customise, brand, deploy ...

# 4. Share learnings in #demo-starter (encouraged!)
```

### Branch Naming Convention

Setup creates a **local branch** to keep your work isolated from `main`:

```
demos/{customer-or-project}-{YYYY-MM}
```

Examples:
- `demos/acme-retail-2026-01`
- `demos/finserv-fraud-2026-02`
- `demos/healthcare-search-2026-01`

> **Note**: Branches are local by default to avoid clutter. Only push if you want to share or preserve the demo long-term.

### What We Track

| Metric | Source | Purpose |
|--------|--------|---------|
| **Repository clones** | GitHub Insights (Traffic) | Adoption volume |
| **Slack activity** | #demo-starter channel | Active usage, questions |
| **Contributions back** | PRs to main or hive-mind | Knowledge growth |
| **Setup completions** | Optional telemetry (TBD) | Success rate |

### Privacy & Data

- Branch names should **not** include sensitive customer details
- Demo data and credentials stay local (`.env` is gitignored)
- No telemetry is sent without explicit opt-in

---

## Success Metrics

### Adoption

| Metric | How to Measure | Target |
|--------|----------------|--------|
| Repository clones | GitHub Insights → Traffic | 50+ per quarter |
| Slack channel members | #demo-starter membership | 50+ |
| Hive Mind contributions | PRs to hive-mind repo | 5+ patterns/quarter |

### Quality

| Metric | How to Measure | Target |
|--------|----------------|--------|
| Demo failure rate | Post-demo survey | <5% |
| Time to troubleshoot | Issue resolution time | <30 min for known issues |
| Pattern reuse rate | Code analysis | >80% use existing patterns |

### Velocity

| Metric | How to Measure | Target |
|--------|----------------|--------|
| Time to first working demo | Setup completion time | <30 minutes |
| Lines of custom code | Diff from main | <200 for typical demo |
| Deployment success rate | Cloud Run deploy logs | >95% |

---

## Roadmap

### Q1 2026 (Current)

- [x] Core framework (React + FastAPI + EUI)
- [x] Agent Builder integration
- [x] Multi-agent orchestration
- [x] Cloud Run deployment
- [ ] Dataset library expansion
- [ ] Fraud analytics demo

### Q2 2026

- [ ] Visual demo builder
- [ ] Demo gallery/showcase
- [ ] Performance benchmarks
- [ ] Additional datasets (fashion, B2B, media)

### Q3 2026

- [ ] One-click deployment templates
- [ ] Customer success stories
- [ ] Advanced personalisation patterns

---

## Contributing Back

If you've solved something tricky or created a reusable pattern, consider contributing it back.

| Situation | Action |
|-----------|--------|
| Fixed a tricky bug | Add to `hive-mind/troubleshooting/` |
| Created a reusable pattern | Add to `hive-mind/patterns/` |
| Found a new dataset | Document in `DEMO_DATASETS.md` |
| Improved the starter itself | PR to `main` branch |

> **Hive Mind contributions** require familiarity with the pattern structure. Ask in #demo-starter if unsure.

---

## Contact & Support

| Channel | Purpose |
|---------|---------|
| **Slack: #demo-starter** | Questions, help, show & tell, pattern discussions |
| **GitHub Issues** | Bug reports, feature requests |

### Repository Links

- **Demo Starter**: [github.com/elastic/elastic-demo-starter](https://github.com/elastic/elastic-demo-starter)
- **Hive Mind**: [github.com/elastic/hive-mind](https://github.com/elastic/hive-mind) (submodule)

---

*This document is the source of truth for project direction. Update it when goals change.*
