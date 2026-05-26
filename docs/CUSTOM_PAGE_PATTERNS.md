# Custom Page Patterns

> How to build domain-specific pages that make demos compelling.

---

## Philosophy

Every demo should have at least one custom page that wouldn't exist in a generic template. Configuring `searchConfig.ts` and `demoPrompts.ts` is table stakes — it makes the demo *work*. A custom page makes the demo *memorable*.

The difference between a demo that gets a polite nod and one that gets a follow-up meeting is almost always a domain-specific experience: a fault diagnosis dashboard, a meal planner, a policy navigator. Something that makes the audience think "this was built for us."

---

## Example UX Proposals

> These are examples of what a build agent should say to an SA during the **UX Design beat** of the build consultation. They're not code — they're conversation templates showing how to pitch a custom page concept with enough detail that the SA can say yes/no before any code is written.

### Example: Pitching a Fault Diagnosis Console (Industrial / Field Service)

> "For the IFS demo, I'd suggest a **Fault Diagnosis Console** as your hero page. Here's why:
>
> **The hook**: An engineer types in a symptom — 'vibration at high RPM on turbine #3' — and gets a split-screen experience. Left side: severity-colored search results with repair time estimates. Right side: an AI advisor that walks through the diagnosis step by step, citing specific fault records.
>
> **Why the audience will care**: This is their 'Moment of Service' use case made tangible. Azure AI Search can't do hybrid search with both part number matching (keyword) and symptom description understanding (semantic) in the same query. We show both in one screen.
>
> **The data**: We'll use `fault_description` (semantic_text) for natural language matching, `severity` and `equipment_type` as facet cards at the top, and `resolution_procedure` for the advisor's step-by-step walkthrough.
>
> **Hooks**: `useSearchSimple` for the fault search + aggregation cards, `ChatContainer` ref so clicking 'Diagnose' on a result sends it to the chat, `useAgentChat` for the advisor conversation."

### Example: Pitching a Meal Planner (Retail / Grocery)

> "For this grocery demo, I'd suggest a **Weekly Meal Planner** page. Here's the concept:
>
> **The hook**: The shopper tells the AI 'I want healthy meals for a family of four, under 30 minutes each'. The assistant suggests recipes and the shopper drags them onto a weekly calendar. Once the plan is set, one click generates a combined shopping list.
>
> **Why the audience will care**: This turns search into an experience. Instead of searching 'chicken recipes' and scrolling, the AI curates and the calendar visualises the week. The shopping list is the 'aha moment' — it aggregates ingredients across all meals.
>
> **The data**: `title`, `cuisine`, `diet` (facets), `prep_time` (range filter), `ingredients` (for list aggregation), `image_url` for visual recipe cards.
>
> **Hooks**: `useA2AChat` with `clientFunctions` — the AI calls `addToMealPlan(recipe, day)` which updates local React state. `useSearchSimple` for a recipe browse panel with cuisine/diet facets."

---

## Available Hooks

The template provides three composable hooks and a ref-based control for building custom pages. Mix and match them to create rich experiences.

### `useAgentChat` — Chat State

**File**: `frontend/src/hooks/useAgentChat.ts`

Single-agent chat with Elastic Agent Builder. Handles streaming, tool calls, and reasoning steps.

```typescript
import { useAgentChat } from '../hooks/useAgentChat'

const {
  messages,           // Message[] — chat history (user + assistant messages)
  isLoading,          // boolean — true while streaming a response
  conversationId,     // string | undefined — current conversation ID
  sendMessage,        // (content: string) => Promise<void> — send a user message
  cancelStream,       // () => void — abort the current stream
  resetConversation,  // () => void — clear history, start fresh
} = useAgentChat({
  initialGreeting: "Hello! I'm your domain assistant.",  // optional
})
```

**Message shape**:
```typescript
interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  reasoning?: string[]          // LLM reasoning steps (if visible)
  toolCalls?: ToolCall[]        // tools the agent invoked
  isComplete: boolean
  error?: string
}
```

### `useSearchSimple` — Search State

**File**: `frontend/src/hooks/useSearchSimple.ts`

Search with filters, facets, sorting, and pagination. Talks to `POST /api/search`.

```typescript
import { useSearchSimple } from '../hooks/useSearchSimple'

const {
  // State
  query,              // string — current search query
  results,            // SearchHit[] — array of {id, score, source, highlight}
  total,              // number — total matching documents
  page,               // number — current page
  totalPages,         // number — total pages
  loading,            // boolean — search in progress
  error,              // string | null — error message
  aggregations,       // Record<string, AggregationBucket[]> — facet buckets
  tookMs,             // number | null — query time in ms

  // Filters & Sort
  filters,            // SearchFilters — active filters
  sortBy,             // string | null — current sort field
  sortDir,            // 'asc' | 'desc' — sort direction

  // Actions
  setQuery,           // (query: string) => void
  search,             // () => Promise<void> — execute search
  setPage,            // (page: number) => void
  setFilter,          // (field: string, value: unknown) => void
  setSort,            // (field: string | null, dir?: 'asc' | 'desc') => void
  clearFilters,       // () => void
  reset,              // () => void — clear everything
} = useSearchSimple({
  initialQuery: '',
  pageSize: 12,
  autoSearch: false,    // set true to re-search on filter/sort/page change
})
```

### `useA2AChat` — Multi-Agent Orchestration

**File**: `frontend/src/hooks/useA2AChat.ts`

Coordinator LLM that routes to multiple Agent Builder agents via function calling. Supports client-side functions for browser-executed actions.

```typescript
import { useA2AChat } from '../hooks/useA2AChat'

const {
  messages,           // A2AMessage[] — includes function call details
  isLoading,          // boolean
  conversationId,     // string | undefined
  sendMessage,        // (content: string) => Promise<void>
  cancelStream,       // () => void
  resetConversation,  // () => void
} = useA2AChat({
  initialGreeting: "I can coordinate multiple specialists.",
  selectedAgents: ['agent-1', 'agent-2'],      // which agents to expose
  systemPrompt: "You are a domain coordinator.",
  clientFunctions: [...],                       // browser-side functions
  onClientFunctionCall: (name, args) => {...},  // handler for client functions
  endpoint: '/api/custom-endpoint',             // custom API route
})
```

### `ChatContainer` Ref — External Message Triggers

**File**: `frontend/src/components/chat/ChatContainer.tsx`

The `ChatContainer` component exposes a ref that lets you send messages programmatically — useful for demo prompt pills, button clicks, or sidebar triggers.

```typescript
import { useRef } from 'react'
import { ChatContainer, ChatContainerRef } from '../components/chat/ChatContainer'

const chatRef = useRef<ChatContainerRef>(null)

// Send a message from outside the chat
const handlePromptClick = (prompt: string) => {
  chatRef.current?.sendMessage(prompt)
}

return (
  <>
    <PromptPills onClick={handlePromptClick} />
    <ChatContainer ref={chatRef} title="Domain Assistant" />
  </>
)
```

### Composability Examples

**Chat + Search** (most common): Use `useAgentChat` for the conversational AI and `useSearchSimple` for a side panel of search results. The chat answers questions; the search panel lets users browse and filter.

**Chat + External Triggers**: Use `ChatContainer` with a ref and add domain-specific buttons that pre-fill chat messages. A "Diagnose this fault" button sends the fault code to the agent.

**Multi-Agent + Search**: Use `useA2AChat` with multiple specialist agents and `useSearchSimple` for a supporting search panel. The coordinator routes questions to the right specialist while the search provides browsable context.

**Search + Client Functions**: Use `useA2AChat` with `clientFunctions` to let the LLM trigger browser-side actions (add to cart, save to list, navigate to detail view) based on search results.

---

## 4 Levels of Customization

Use the lightest level that achieves the goal. Most demos need levels 1 and 3.

### Level 1: Config-only (always do this)

Edit configuration files — no new components needed.

| File | What to configure |
|------|-------------------|
| `frontend/src/config/searchConfig.ts` | Index name, search fields, display mapping, facets, range filters, sort options |
| `frontend/src/config/demoConfig.ts` | `NAV_PAGES` (which pages to show), `DEMO_TITLE`, `DEMO_SUBTITLE` |
| `frontend/src/config/demoPrompts.ts` | Domain-specific chat prompts and suggested questions |

**When**: Every demo. This is the baseline.

### Level 2: Recompose existing pages

Rearrange, add sections to, or conditionally render parts of existing page components.

- Add a hero section or domain introduction to `WelcomePage`
- Split `SearchPageSimple` into a two-column layout with chat alongside results
- Add custom result rendering logic to the search page

**When**: The existing page structure is close but needs layout tweaks.

### Level 3: Custom pages from hooks (the sweet spot)

Create a new `.tsx` page that composes hooks directly. This is where domain-specific magic happens.

```
frontend/src/pages/FaultDiagnosisPage.tsx     # New page
frontend/src/config/navigationConfig.ts        # Register in nav (if used)
frontend/src/App.tsx                           # Add route
```

**When**: You need an experience that doesn't map to any existing page. Most demos should have at least one of these.

### Level 4: New components

Build entirely new UI components — custom result cards, domain visualizations, interactive widgets.

```
frontend/src/components/domain/SeverityHeatmap.tsx
frontend/src/components/domain/RecipeCard.tsx
frontend/src/components/domain/PolicyFlowChart.tsx
```

**When**: The standard EUI components can't express the domain concept. Use sparingly — EUI covers most needs.

---

## Example Custom Pages

### Fault Diagnosis Dashboard (Industrial / Field Service)

**What it does**: An engineer enters a fault code or describes a symptom. The page shows a severity heatmap of related faults, a chat advisor that walks through diagnosis steps, and a parts search for replacement components.

**Layout**:
```
┌─────────────────────────────────────────────┐
│  Fault Diagnosis Dashboard                  │
├──────────────────────┬──────────────────────┤
│                      │                      │
│  Severity Heatmap    │  Chat Advisor        │
│  (search aggs)       │  (useAgentChat)      │
│                      │                      │
├──────────────────────┴──────────────────────┤
│  Related Parts Search (useSearchSimple)     │
│  [filters: category, severity, availability]│
└─────────────────────────────────────────────┘
```

**Hooks used**:
- `useAgentChat` — diagnosis chat with domain system prompt
- `useSearchSimple` — parts/faults search with severity aggregations
- `ChatContainer` ref — "Diagnose this fault" buttons trigger chat messages

**Key data fields**: `fault_code`, `severity`, `equipment_type`, `resolution_steps`, `parts_required`

### Meal Planner (Retail / Grocery)

**What it does**: A shopper describes what they want to eat this week. The chat suggests recipes, which appear as draggable cards. The shopper builds a weekly plan and generates a shopping list from the combined ingredients.

**Layout**:
```
┌─────────────────────────────────────────────┐
│  Weekly Meal Planner                        │
├────────────┬────────────────────────────────┤
│            │  Mon  Tue  Wed  Thu  Fri       │
│  Chat      │  ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐    │
│  (useA2A)  │  │  │ │  │ │  │ │  │ │  │    │
│            │  └──┘ └──┘ └──┘ └──┘ └──┘    │
│            ├────────────────────────────────┤
│            │  Shopping List                 │
│            │  (aggregated ingredients)      │
└────────────┴────────────────────────────────┘
```

**Hooks used**:
- `useA2AChat` with `clientFunctions` — chat suggests recipes, `addToMealPlan` client function adds them to the calendar
- `useSearchSimple` — recipe search with cuisine/diet/time facets
- Local React state — meal plan grid, shopping list aggregation

**Key data fields**: `title`, `cuisine`, `diet`, `prep_time`, `ingredients`, `image_url`, `servings`

### Policy Navigator (Insurance / Public Sector)

**What it does**: A citizen answers guided questions about their situation. The page narrows down relevant policies, shows matching documents with highlighted sections, and provides plain-language explanations via chat.

**Layout**:
```
┌─────────────────────────────────────────────┐
│  Policy Navigator                           │
├────────────┬────────────────────────────────┤
│            │                                │
│  Guided    │  Matching Policies             │
│  Questions │  (useSearchSimple, filtered)   │
│  (wizard)  │                                │
│            ├────────────────────────────────┤
│            │  Ask About This Policy         │
│            │  (ChatContainer + ref)         │
└────────────┴────────────────────────────────┘
```

**Hooks used**:
- `useSearchSimple` — policy search, filters narrow as the user answers questions
- `ChatContainer` ref — clicking a policy result sends "Explain policy X in plain language" to the chat
- Local React state — wizard step tracking, selected answers

**Key data fields**: `policy_name`, `category`, `eligibility_criteria`, `coverage_details`, `effective_date`, `plain_summary`

---

## Registering a Custom Page

### 1. Create the page component

```
frontend/src/pages/MyCustomPage.tsx
```

```typescript
import { EuiPageTemplate, EuiTitle } from '@elastic/eui'
import { useAgentChat } from '../hooks/useAgentChat'
import { useSearchSimple } from '../hooks/useSearchSimple'

/**
 * AppHeader is rendered automatically by the Layout wrapper in App.tsx.
 * Do NOT import or render AppHeader in page components.
 */
export function MyCustomPage() {
  const chat = useAgentChat({ initialGreeting: "How can I help?" })
  const search = useSearchSimple({ autoSearch: true })

  return (
    <EuiPageTemplate>
      <EuiPageTemplate.Header>
        <EuiTitle><h1>My Custom Page</h1></EuiTitle>
      </EuiPageTemplate.Header>
      <EuiPageTemplate.Section>
        {/* Your domain-specific layout here */}
      </EuiPageTemplate.Section>
    </EuiPageTemplate>
  )
}
```

### 2. Add the route in `App.tsx`

All standard routes are nested inside `<Route element={<Layout />}>`, which renders `AppHeader` automatically. Just add your route inside that group:

```typescript
import { MyCustomPage } from './pages/MyCustomPage'

// Inside <Route element={<Layout />}>:
<Route path="/my-custom" element={<MyCustomPage />} />
```

> **Headerless routes**: If a page genuinely needs no header (e.g. an embedded widget),
> place its `<Route>` outside the `<Route element={<Layout />}>` group.

### 3. Add to navigation

The app header reads from `demoConfig.ts` to decide which pages to show. Add your path to `NAV_PAGES`:

```typescript
// frontend/src/config/demoConfig.ts
export const NAV_PAGES: string[] | null = ['/', '/guide', '/search', '/chat', '/my-custom']
```

If the app uses a navigation config file, add an entry there too:

```typescript
{ label: 'My Custom', path: '/my-custom', icon: 'grid' }
```

### 4. Register any new EUI icons

If your page uses EUI icons not already in the cache, add them to `frontend/src/iconCache.ts` or restart the dev server (it auto-generates the cache on start).

---

## Styling Guidelines

> See also:
> - `CLAUDE.md` → **Visual Quality Standards** for mandatory rules during page construction
> - `docs/PAGE_RECIPES.md` → Standard layout patterns with component imports and spacing values
> - `docs/DEMO_PAGE_VISUAL_DESIGN.md` → CSS variable reference, typography scale, spacing system, dark mode rules

### Use brand CSS variables

Custom pages should respect the active brand theme. Use CSS variables set by `BrandContext`:

```css
.my-custom-header {
  background: var(--brand-primary, #0077CC);
  color: var(--brand-on-primary, #FFFFFF);
}

.my-custom-accent {
  border-color: var(--brand-accent, #00BFB3);
}
```

For dark mode compatibility, always use EUI variables as the inner fallback:
```tsx
style={{
  color: 'var(--brand-text-body, var(--euiTextColor))',
  background: 'var(--brand-background, var(--euiColorEmptyShade))',
  borderColor: 'var(--brand-border, var(--euiColorLightShade))',
}}
```

See `hive-mind/patterns/eui/DEMO_PAGE_VISUAL_DESIGN.md` for the full CSS variable reference and known component exceptions (e.g. `EuiAvatar` requires hex colours).

### Prefer EUI components

EUI handles responsive layout, dark mode, accessibility, and theme consistency. Use EUI for structure and only drop to custom CSS for domain-specific visuals:

- `EuiPageTemplate` — page structure
- `EuiFlexGroup` / `EuiFlexItem` — flexible layouts
- `EuiPanel` — content containers
- `EuiStat` — metric displays
- `EuiBadge` — status indicators
- `EuiCard` — result cards
- `EuiAccordion` — collapsible sections

### Make it look like a product, not a prototype

Demo pages should include domain-relevant imagery from the start — not as a polish step. Text-only pages feel like wireframes. Apply these during initial construction:

**Start with a recipe**: Read `docs/PAGE_RECIPES.md` and pick the closest layout recipe before writing code. Build the visual scaffold first (hero + sections + placeholder images), then wire data.

**Hero banners**: Use `HeroSection` from `components/common/HeroSection.tsx` — it handles background photos, brand overlays, and gradient fallbacks automatically. Every landing page and dashboard should have one.

**Feature grids**: Use `FeatureGrid` from `components/common/FeatureGrid.tsx` for responsive card layouts with images. Handles 3-col/2-col/1-col responsively with image error fallbacks built in.

**Photo strips**: Use `PhotoStrip` from `components/common/PhotoStrip.tsx` — small circular images in a horizontal row work well for categories, inspiration, or featured items.

**Card imagery**: Result cards, product cards, and recipe cards should include thumbnail images wherever the data provides image URLs. Minimum 2 visual elements per card (see `docs/DEMO_PAGE_VISUAL_DESIGN.md`).

**Empty states**: Use `BrandedEmptyState` from `components/common/BrandedEmptyState.tsx` — supports icon, image, and photo strip modes with actionable text. Never leave bare "no data" text.

**Chat persona**: Give the assistant a name, custom avatar (SVG or image via `assistantAvatarUrl` prop), and a greeting that references the demo persona by name. This makes the chat feel purpose-built rather than generic.

**Image sources**: Use `unsplash()` and `STOCK_IMAGES` from `utils/images.ts` (14 domain categories, 70+ curated photos). Use `getStockCategory(domain)` to find the best category for your demo. Always add `loading="lazy"` to decorative images. For demos shown to live audiences, download key images to `public/images/` to avoid Unsplash rate limits.

### Fixed header layout

The app header is rendered by the `Layout` wrapper and is `position: fixed` at ~56px. Pages do NOT render `AppHeader` themselves — it's structural.

Content that doesn't account for the header height will be hidden behind it.

**For full-viewport layouts** (e.g. chat + sidebar pages): Use separate `position: fixed` containers with explicit `top` values. Don't rely on EUI generating spacer divs — in React fragment structures the spacer may not render.

```tsx
{/* AppHeader is already rendered by Layout — do NOT add it here */}
<div style={{ position: 'fixed', top: 56, left: 0, right: 0, /* secondary bar */ }}>
<div style={{ position: 'fixed', top: 96, left: 0, right: 0, bottom: 0, overflow: 'hidden' }}>
  {/* Main content */}
</div>
```

**For standard pages**: Use `EuiPageTemplate` which handles the offset automatically. The fixed layout is only needed for custom full-viewport designs.

### Sidebar constraints

Always set `minWidth` and `maxWidth` on sidebar panels to prevent overflow or collapse:

```tsx
<EuiFlexItem grow={4} style={{ minWidth: 320, maxWidth: 480 }}>
```

### Responsive patterns

Test at three breakpoints: mobile (< 768px), tablet (768-1024px), desktop (> 1024px). EUI's `EuiFlexGroup` with `wrap` handles most cases. For complex layouts, use `EuiShowFor` / `EuiHideFor` to adapt.

---

## Checklist for Custom Pages

- [ ] Page component created in `frontend/src/pages/`
- [ ] Route added inside `<Route element={<Layout />}>` in `App.tsx`
- [ ] Page does NOT import or render `AppHeader` (Layout handles this)
- [ ] Page path added to `NAV_PAGES` in `demoConfig.ts`
- [ ] Hooks connected and data flowing
- [ ] Brand CSS variables used (not hardcoded colours)
- [ ] EUI components used for layout
- [ ] Responsive at mobile, tablet, and desktop widths
- [ ] New EUI icons registered in icon cache
- [ ] Page works with the demo's actual data (not mock data)
