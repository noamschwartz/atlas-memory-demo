# UI Audit: Page Sizes, Refactoring Opportunities & Missing Components

> **Bead**: elastic-agent-starter-zx8
> **Date**: 2026-02-06
> **Scope**: Research only -- no code changes

---

## 1. Pages Sorted by Line Count

| # | Page | Path | Lines | Over 300? | Demo Use Case |
|---|------|------|------:|:---------:|---------------|
| 1 | OverlayGuidePage | `pages/OverlayGuidePage.tsx` | 736 | YES | Tampermonkey injection guide with script generator |
| 2 | MCPExplorerPage | `pages/MCPExplorerPage.tsx` | 638 | YES | MCP server tool browser & tester |
| 3 | DemoGuidePage | `pages/DemoGuidePage.tsx` | 626 | YES | Presenter guide with demo tracks |
| 4 | BrandEditorPage | `pages/BrandEditorPage.tsx` | 608 | YES | Visual brand theme editor |
| 5 | WelcomePage | `pages/WelcomePage.tsx` | 575 | YES | Landing page with feature cards |
| 6 | SearchPageSimple | `pages/SearchPageSimple.tsx` | 438 | YES | Faceted search with field discovery |
| 7 | OverlayDemoPage | `pages/OverlayDemoPage.tsx` | 327 | YES | FloatingChatWidget showcase |
| 8 | BrandedDemoPage | `pages/BrandedDemoPage.tsx` | 242 | no | Full-screen branded demo |
| 9 | A2AChatPage | `pages/A2AChatPage.tsx` | 191 | no | Multi-agent orchestration |
| 10 | AuditPage | `pages/AuditPage.tsx` | 169 | no | Conversation history viewer |
| 11 | ChatPage | `pages/ChatPage.tsx` | 75 | no | Single-agent chat |

**Total page code**: 4,625 lines across 11 pages.
**Pages over 300 lines**: 7 of 11 (64%).

---

## 2. Large Components (Over 250 Lines)

| Component | Path | Lines | Notes |
|-----------|------|------:|-------|
| FloatingChatWidget | `components/chat/FloatingChatWidget.tsx` | 610 | Self-contained chat overlay, renders its own messages and input |
| BrandedThemeProvider | `components/providers/BrandedThemeProvider.tsx` | 421 | Brand context + CSS variable injection, heavy but structural |
| FunctionCallCard | `components/a2a/FunctionCallCard.tsx` | 383 | A2A function call rendering with agent steps |
| A2AChatContainer | `components/a2a/A2AChatContainer.tsx` | 382 | A2A chat with health check and agent selector |
| AgentSelector | `components/a2a/AgentSelector.tsx` | 367 | Multi-select for coordinator agents |
| ConversationDetail | `components/audit/ConversationDetail.tsx` | 305 | Full conversation view with reasoning and tool calls |
| SearchResultCard | `components/search/SearchResultCard.tsx` | 296 | Product card with generic JSON fallback |
| ChatContainer | `components/chat/ChatContainer.tsx` | 253 | Core chat with SSE streaming |

---

## 3. Top Refactoring Candidates (Biggest Bang for Buck)

### Priority 1: OverlayGuidePage (736 lines)

**Why it's large**: Contains 4 inline EuiSteps children (Install, Configure, Copy Script, Test), a full troubleshooting section (5 panels), and customisation accordions -- all as JSX literals inside the component.

**What to extract**:
- The step definitions (lines 159-463) are large JSX objects. They could be extracted into separate components (`OverlayGuideStep1Install`, `OverlayGuideStep2Configure`, etc.) or a separate data file.
- The troubleshooting panels (lines 641-702) are a repeated pattern: `EuiPanel color="subdued" paddingSize="m"` with a bold title and bullet list. This repeats 5 times and could be a `TroubleshootingPanel` component.
- The colour swatch preview (inline div with `width: 20, height: 20, backgroundColor, borderRadius: 4, border`) is repeated in BrandEditorPage too.

**Estimated reduction**: ~300 lines (down to ~430).

### Priority 2: MCPExplorerPage (638 lines)

**Why it's large**: Contains 105 lines of TypeScript interfaces (lines 57-104), all fetch/test logic (3 useCallback handlers), and a dense two-column layout with connection status, config tabs, tools summary, and tool tester all in one file.

**What to extract**:
- Types and API functions (lines 57-155) into a `services/mcpApi.ts` file (~100 lines).
- Tool Tester panel (lines 453-629) into a `components/mcp/ToolTester.tsx` component (~180 lines).
- Connection Status + Config panel (lines 292-448) into `components/mcp/MCPConnectionPanel.tsx` (~160 lines).

**Estimated reduction**: ~440 lines (down to ~200 as an orchestration page).

### Priority 3: BrandEditorPage (608 lines)

**Why it's large**: Contains inline API functions (lines 74-109), a `BrandCard` sub-component (lines 115-182), a full `BrandEditorModal` sub-component (lines 188-413) with 4 colour picker fields each using the identical swatch pattern, and the main page component.

**What to extract**:
- API functions into `services/brandingApi.ts` (already partially covered by `routes/branding.py` backend; the frontend fetch wrappers are not shared).
- `BrandCard` and `BrandEditorModal` into `components/branding/BrandCard.tsx` and `components/branding/BrandEditorModal.tsx`.
- The color picker with swatch is repeated 4 times (lines 280-365). Extract a `ColorPickerField` component.

**Estimated reduction**: ~350 lines (down to ~250).

### Priority 4: DemoGuidePage (626 lines)

**Why it's large**: Contains ~170 lines of track configuration data (the `DEMO_TRACKS` array, lines 123-293), three local sub-components (`DemoPill`, `ResourceLink`, `DemoSection`), and the main component.

**What to extract**:
- Track data into a config file `config/demoTracks.ts` (~170 lines).
- `DemoSection` component into `components/demo/DemoSection.tsx` (~90 lines). This is the only non-trivial component among the three locals.

**Estimated reduction**: ~260 lines (down to ~360).

### Priority 5: WelcomePage (575 lines)

**Why it's large**: Contains ~90 lines of feature configuration data (the `FEATURES` array), health check logic, and 3 collapsible sections (Features, Setup, Vibe Coding).

**What to extract**:
- Feature definitions into `config/features.ts` (~90 lines).
- The "Setup & Onboarding" and "Vibe Coding Tips" accordion content could become separate components, but these are presentational and changing infrequently. Lower priority.

**Estimated reduction**: ~100 lines (down to ~475). Moderate benefit.

### Priority 6: FloatingChatWidget (610 lines -- component, not page)

**Why it's large**: Renders its own message bubbles, input area, and FAB with all CSS inline. This is intentional (standalone embeddable widget), but the message rendering logic duplicates `MessageBubble` and `MarkdownContent` from the chat components.

**What to extract**: The message rendering inside FloatingChatWidget (simplified markdown, message layout) duplicates patterns from `ChatContainer`/`MessageBubble`. Consider sharing a lightweight message renderer. However, the widget is designed to be self-contained for injection use cases, so this trade-off may be intentional.

**Recommendation**: Document the duplication but do not refactor unless the widget needs feature parity with the main chat.

---

## 4. Duplicated Patterns Worth Extracting

### 4.1 Page Shell Pattern (all 11 pages)

Every page follows this skeleton:
```tsx
<>
  <AppHeader />
  <EuiSpacer size="xxl" />
  <EuiSpacer size="l" />
  <EuiPageTemplate restrictWidth={N} panelled={false}>
    <EuiPageTemplate.Section>
      {/* content */}
    </EuiPageTemplate.Section>
  </EuiPageTemplate>
</>
```

The `AppHeader` + double spacer + `EuiPageTemplate` wrapper is repeated in 9 of 11 pages (MCPExplorerPage and AuditPage use `EuiPage` instead). Extracting a `PageShell` wrapper component would:
- Standardise the header offset (currently the double spacer is the convention for fixed header clearance)
- Allow consistent `restrictWidth` defaults
- Reduce 6 lines per page (small but consistent)

**Impact**: Low per-page, but high consistency gain across the codebase.

### 4.2 Colour Swatch Preview (BrandEditorPage, OverlayGuidePage, BrandedDemoPage)

Three files render small coloured squares as brand previews using inline styles:
```tsx
<div style={{ width: N, height: N, backgroundColor: color, borderRadius: 4, border: '1px solid #ccc' }} />
```

This appears 4 times in BrandEditorPage (modal colour pickers), 1 time in OverlayGuidePage (primary colour field), and once in BrandedDemoPage (brand info panel). A `ColorSwatch` component would eliminate the repetition.

**Impact**: Small (removes ~5 lines each), but improves maintainability.

### 4.3 Troubleshooting Panel Pattern (OverlayGuidePage)

Five troubleshooting items use the identical layout:
```tsx
<EuiPanel color="subdued" paddingSize="m">
  <strong>Title</strong>
  <ul>
    <li>Item</li>
    ...
  </ul>
</EuiPanel>
```

This pattern is used only in OverlayGuidePage today but would be useful for any new guide pages.

**Impact**: Medium -- cleans up the largest file by ~100 lines.

### 4.4 Feature Card Grid (WelcomePage, DemoGuidePage)

Both pages render grids of EuiCard components with icon + title + description + footer. The card layout is similar but not identical (WelcomePage has status badges, DemoGuidePage has track badges). Worth watching for convergence but not ready to extract yet.

### 4.5 API Fetch Wrappers (BrandEditorPage, MCPExplorerPage)

Both pages define inline `async function` wrappers for fetch calls. `BrandEditorPage` has 4 API functions (fetchBrands, createBrand, updateBrand, deleteBrand), and `MCPExplorerPage` has 3 (fetchMCPInfo, fetchTools, testTool). These should live in `services/` alongside the existing `agentApi.ts`, `auditApi.ts`, and `analyticsApi.ts`.

**Impact**: Medium -- improves testability and follows the established service pattern.

---

## 5. Mapping Pages to Demo Use Cases

| Demo Scenario (from Feature Catalog) | Primary Page | Supporting Pages |
|---------------------------------------|-------------|-----------------|
| Agent Chat | ChatPage | AuditPage |
| Multi-Agent (A2A) | A2AChatPage | AuditPage |
| MCP Tools | MCPExplorerPage | ChatPage |
| Product/Content Search | SearchPageSimple | -- |
| Overlay on Customer Site | OverlayGuidePage | OverlayDemoPage |
| Custom Branding | BrandEditorPage | BrandedDemoPage |
| Branded Presentation | BrandedDemoPage | BrandEditorPage |
| Demo Flow / Presenter Guide | DemoGuidePage | All pages |
| Conversation Audit | AuditPage | ChatPage, A2AChatPage |
| Landing / Onboarding | WelcomePage | -- |

---

## 6. Missing UI Components for Common Demo Scenarios

### 6.1 Analytics / Dashboard Page (HIGH priority)

The backend has `routes/analytics.py` with ES|QL search analytics (CTR, MRR, zero-results, top queries), and there is a `services/analyticsApi.ts` frontend service. But there is **no analytics dashboard page**. The Feature Catalog lists "Search Analytics" as a feature, and the value propositions highlight "real-time insights" as a universal wow moment.

**What's needed**: An `AnalyticsDashboardPage` displaying search performance metrics (click-through rate, mean reciprocal rank, zero-result queries, popular queries) using the existing `analyticsApi` service.

### 6.2 Search + Chat Combined View (MEDIUM priority)

The value propositions (especially retail, tech/SaaS) emphasise "AI assistant with search grounding" as a key demo combo. Currently, search and chat are entirely separate pages. A combined view where search results feed into agent context (or a chat sidebar alongside search) would strengthen the "search + AI" narrative.

**What's needed**: Either a layout variant of SearchPageSimple with a chat sidebar, or a way to launch chat from a search result with context pre-loaded.

### 6.3 Workflow Visualization (MEDIUM priority)

Every vertical in the value propositions highlights "Agent + Workflow automation" as a key demo moment. There is no UI for visualising or triggering Elastic Workflows from the demo app. The A2A architecture graph is a step toward this, but it shows agent topology rather than workflow execution.

**What's needed**: A Workflows page or panel that shows workflow triggers, execution status, and integration with agent actions.

### 6.4 ES|QL Query Explorer (LOW priority)

The value propositions highlight "ES|QL from natural language" as a universal wow moment (point 3 in the cross-vertical reference). The backend supports ES|QL via the analytics routes, but there is no interactive ES|QL query page where a user can type natural language and see the generated ES|QL and results.

**What's needed**: An ES|QL explorer that demonstrates natural language to ES|QL translation.

### 6.5 Personalisation Demo (LOW priority)

The Feature Catalog lists "Personalisation Tracking" and there is an OTel pattern for it, but no UI to demonstrate personalised results or A/B test variants to a customer.

---

## 7. Component Registry Maturity Gaps

Cross-referencing with `docs/COMPONENT_REGISTRY.md`:

- **All components are listed as "Production"** -- there are no "Working", "Experimental", or "Stub" entries in the frontend section. This seems optimistic given that some components (e.g., AgentArchitectureGraph at 184 lines) are relatively thin.
- **Missing from registry**: The `DemoPromptPills` component is in the registry, but the inline sub-components in `DemoGuidePage` (`DemoPill`, `ResourceLink`, `DemoSection`) are not, despite being reusable.
- **No analytics components** exist despite the backend analytics route being Production status.
- **`agno_demo.py`** is marked "Experimental" in the backend registry, but has no corresponding frontend page.

---

## 8. Prioritised Recommendations

| Priority | Action | Effort | Impact | Notes |
|:--------:|--------|:------:|:------:|-------|
| **P1** | Extract MCP types + API into `services/mcpApi.ts`, split MCPExplorerPage into panels | S | High | Follows existing service pattern; largest cleanup opportunity |
| **P1** | Extract BrandEditorPage API into `services/brandingApi.ts`, split modal and card | S | High | 4 inline API functions + 2 sub-components already well-separated |
| **P2** | Create `AnalyticsDashboardPage` using existing `analyticsApi` | M | High | Backend ready, service ready, zero UI -- most impactful new page |
| **P2** | Extract OverlayGuidePage step content and troubleshooting panels | S | Med | Largest file; step content is self-contained |
| **P2** | Move DemoGuidePage track data into `config/demoTracks.ts` | XS | Med | Pure data extraction, trivial change |
| **P3** | Create `PageShell` wrapper for the AppHeader + spacer + PageTemplate pattern | S | Med | Consistency across 9 pages |
| **P3** | Create `ColorSwatch` component for the repeated colour preview pattern | XS | Low | Small but eliminates subtle inconsistencies |
| **P3** | Move WelcomePage features array into `config/features.ts` | XS | Low | Pure data extraction |
| **P4** | Add Search+Chat combined layout variant | M | High | Requires design thinking; key for "AI with search grounding" demos |
| **P4** | Add Workflow visualisation page/panel | L | High | Depends on Elastic Workflows API availability |
| **P4** | Audit COMPONENT_REGISTRY.md maturity ratings | XS | Med | Some "Production" labels may be premature |

**Effort key**: XS = <30 min, S = 1-2 hours, M = half day, L = 1+ day

---

## Summary

The codebase has 11 pages totalling 4,625 lines. Seven pages exceed 300 lines, with the top three (OverlayGuidePage, MCPExplorerPage, BrandEditorPage) each exceeding 600 lines and containing inline sub-components, API wrappers, or large data definitions that belong in separate files.

The most impactful changes are:
1. **Extract service layers** for MCP and Branding pages (follows existing patterns for `agentApi`, `auditApi`, `analyticsApi`)
2. **Build the missing analytics dashboard** (backend + frontend service exist; just needs the page)
3. **Split the largest pages** into orchestration pages + extracted components

The project's established pattern of small, focused components (e.g., ChatPage at 75 lines delegating to ChatContainer) should be the model for all pages.
