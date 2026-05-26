# Page Reference

> Documentation for demo builders: what each page does and how to customize it.
>
> **Not sure which pages you need?** See the [Feature Catalog](./FEATURE_CATALOG.md) first.

______________________________________________________________________

## Quick Reference: Which Pages Do I Need?

**Building an overlay/injection demo?**
You probably don't need most pages. The overlay chat connects directly to `/api/agent/chat`. You might use:
- **Brand Editor** (`/brands`) — Optional, to match customer colors in the overlay

**Building a standalone search + chat demo?**
- **Chat** (`/chat`) — Main AI interface
- **Search** (`/search`) — If you have an ES index to search
- **Brand Editor** (`/brands`) — Customer branding
- **Demo Guide** (`/guide`) — Your presenter notes

**Building a multi-agent demo?**
- **A2A Chat** (`/a2a-chat`) — Multi-agent orchestration
- **Audit** (`/audit`) — See which agent handled what
- **Chat** (`/chat`) — Single-agent comparison

**Just exploring/testing?**
- **Welcome** (`/`) — Status dashboard, feature overview
- **MCP Explorer** (`/mcp`) — Browse available tools

______________________________________________________________________

## Overview

The demo starter includes these pages:

| Page                               | Path        | Purpose                        | Requires          |
| ---------------------------------- | ----------- | ------------------------------ | ----------------- |
| [Welcome](#welcome-page)           | `/`         | Feature showcase & onboarding  | Nothing           |
| [Demo Guide](#demo-guide-page)     | `/guide`    | Presenter guide with demo flow | Nothing           |
| [Chat](#chat-page)                 | `/chat`     | Agent Builder chat interface   | Agent connection  |
| [Branded Demo](#branded-demo-page) | `/branded`  | Full-screen presentation mode  | Agent connection  |
| [Brand Editor](#brand-editor-page) | `/brands`   | Create/manage brand themes     | Nothing           |
| [Audit](#audit-page)               | `/audit`    | Review conversation history    | Agent connection  |
| [MCP Explorer](#mcp-explorer-page) | `/mcp`      | Browse MCP server tools        | Agent connection  |
| [A2A Chat](#a2a-chat-page)         | `/a2a-chat` | Multi-agent orchestration      | Agent + LLM Proxy |
| [Search](#search-page)             | `/search`   | Elasticsearch search UI        | ES connection     |

______________________________________________________________________

## Welcome Page

**Path**: `/`\
**File**: `frontend/src/pages/WelcomePage.tsx`\
**Category**: Core

### Purpose

The landing page that shows:

- Connection status (Agent Builder, LLM Proxy)
- Available features organized by category
- Setup guidance (collapsible)
- Vibe coding tips (collapsible)

### When to Use

- Default landing for new users
- Quick status check for the demo environment
- Jumping-off point to other features

### Customization

**Change the feature list**: Edit the `FEATURES` array in `WelcomePage.tsx`

```typescript
const FEATURES: Feature[] = [
  {
    id: 'my-feature',
    path: '/my-feature',
    title: 'My Feature',
    description: 'What it does...',
    icon: 'sparkles',  // EUI icon name
    category: 'demo',  // 'demo' | 'tools' | 'advanced'
    requirements: { agentConnection: true },
    useCase: 'When to use this feature',
  },
  // ...
]
```

**Change category labels**: Edit `CATEGORY_LABELS` in the same file.

______________________________________________________________________

## Demo Guide Page

**Path**: `/guide`\
**File**: `frontend/src/pages/DemoGuidePage.tsx`\
**Category**: Tools

### Purpose

A presenter's guide for demonstrating the application:

- Demo overview and capabilities
- Structured demo flow with numbered scenarios
- Talking points for each section
- Quick-launch buttons ("demo pills") to jump to specific pages
- Resource links to documentation

### When to Use

- Before giving a demo (to prepare)
- During a demo (as a reference)
- Training others on how to demo the product
- Self-guided exploration of features

### Customization

This page is designed to be heavily customized! Edit `DemoGuidePage.tsx`:

**Change demo info**:

```typescript
const DEMO_CONFIG = {
  title: 'My Demo Guide',
  subtitle: 'Custom subtitle for your demo',
  overview: 'What this demo shows...',
  capabilities: ['Capability 1', 'Capability 2'],
}
```

**Add demo scenarios**:

```typescript
const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: 'my-scenario',
    badge: '1',
    badgeColor: 'primary',
    title: 'My Demo Scenario',
    keyInsight: 'The main point to communicate',
    steps: ['Step 1', 'Step 2', 'Step 3'],
    talkingPoints: ['Point to mention', 'Another point'],
    demoPills: [
      { label: 'Open Chat', path: '/chat' },
      { label: 'Search "laptop"', path: '/search', query: 'laptop' },
    ],
    resources: [
      { label: 'Documentation', href: 'https://...', type: 'docs' },
    ],
  },
]
```

**Add resource links**:

```typescript
const RESOURCES = {
  myFeature: {
    docs: 'https://elastic.co/docs/...',
    blog: 'https://elastic.co/blog/...',
  },
}
```

### Tips

- Keep scenarios focused on one concept each
- Include specific talking points (what to say out loud)
- Use demo pills to make navigation seamless during presentations
- Update the "Key Messages" section with your top 3-4 points

______________________________________________________________________

## Chat Page

**Path**: `/chat`\
**File**: `frontend/src/pages/ChatPage.tsx`\
**Category**: Demo Building

### Purpose

The primary chat interface for interacting with your Agent Builder agent. Features:

- Streaming responses with real-time text
- Reasoning steps visualization (agent thinking)
- Tool call cards (what tools the agent uses)
- Conversation history
- Stream cancellation

### When to Use

- Main demo interface for most presentations
- Testing agent responses
- Showcasing Agent Builder capabilities

### Customization

See [CUSTOMIZATION.md](./CUSTOMIZATION.md) for detailed options:

```tsx
<ChatContainer
  title="My Assistant"
  greeting="Hello! How can I help?"
  placeholder="Ask me anything..."
  suggestions={[
    { icon: '🔍', label: 'Search', prompt: 'Search for...' },
  ]}
/>
```

**Key customization points**:

- `greeting` - Initial assistant message
- `placeholder` - Input field placeholder text
- `suggestions` - Quick prompt chips
- `emptyState` - Custom empty state component

______________________________________________________________________

## Branded Demo Page

**Path**: `/branded`\
**File**: `frontend/src/pages/BrandedDemoPage.tsx`\
**Category**: Demo Building

### Purpose

A full-screen, presentation-ready version of the chat interface with:

- Brand-specific theming
- Minimal chrome/distractions
- Clean layout for customer presentations

### When to Use

- Customer-facing demos
- Screenshots/videos for marketing
- Showcasing branding capabilities

### Customization

The page automatically uses the currently selected brand. To change brands:

1. **URL parameter**: `http://localhost:3000/branded?brand=myBrandId`
2. **Brand selector**: Use the dropdown in the header
3. **Default brand**: Modify `getSelectedBrandId()` in `frontend/src/branding/index.ts`

______________________________________________________________________

## Brand Editor Page

**Path**: `/brands`\
**File**: `frontend/src/pages/BrandEditorPage.tsx`\
**Category**: Demo Building

### Purpose

Visual editor for creating and managing brand themes:

- Color pickers for primary/accent colors
- Logo upload for light/dark modes
- Live preview
- Brand switching

### When to Use

- Quick brand customization without code
- Non-technical users creating themes
- Rapid prototyping of brand looks

### Storage

Brands created here are stored in `backend/data/brands.json`.

### Limitations

For advanced branding (custom fonts, gradients, CSS variables), use the AI-powered extraction approach instead. See [BRANDING.md](./BRANDING.md).

______________________________________________________________________

## Audit Page

**Path**: `/audit`\
**File**: `frontend/src/pages/AuditPage.tsx`\
**Category**: Development Tools

### Purpose

Review conversation history with full visibility into:

- All messages (user and assistant)
- Agent reasoning steps
- Tool calls and their results
- Timing information

### When to Use

- Debugging agent behavior
- Understanding why an agent gave a certain response
- Reviewing tool usage patterns
- Quality assurance on agent responses

### Data Source

Conversations are retrieved from Agent Builder's conversation API. Only conversations from the configured agent are shown.

______________________________________________________________________

## MCP Explorer Page

**Path**: `/mcp`\
**File**: `frontend/src/pages/MCPExplorerPage.tsx`\
**Category**: Development Tools

### Purpose

Browse and test Model Context Protocol (MCP) server tools:

- List available tools
- View tool schemas (inputs/outputs)
- Test tools with sample inputs

### When to Use

- Discovering what tools your agent has access to
- Testing tool behavior before using in prompts
- Debugging tool-related issues

### Requirements

The agent must have MCP tools configured in Agent Builder.

______________________________________________________________________

## A2A Chat Page

**Path**: `/a2a-chat`\
**File**: `frontend/src/pages/A2AChatPage.tsx`\
**Category**: Advanced

### Purpose

Multi-agent orchestration using Agent-to-Agent (A2A) pattern:

- Coordinator LLM decides which agent to call
- Multiple Agent Builder agents available
- Visual indicator of which agent is responding

### When to Use

- Complex workflows requiring multiple specialized agents
- Demonstrating multi-agent orchestration
- Scenarios where different agents handle different domains

### Requirements

1. **Agent Builder connection** - At least one agent configured
2. **LLM Proxy** - Required for the coordinator:
   - `LLM_PROXY_URL` in `.env`
   - `LLM_PROXY_API_KEY` in `.env`

### Architecture

```text
User Query
    │
    ▼
┌─────────────────┐
│ Coordinator LLM │  (Decides which agent to call)
└────────┬────────┘
         │
    ┌────┴────┬─────────┐
    ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐
│Agent 1│ │Agent 2│ │Agent 3│
└───────┘ └───────┘ └───────┘
```

See `hive-mind/patterns/agent-builder/A2A_COORDINATOR_PATTERN.md` for details.

______________________________________________________________________

## Search Page

**Path**: `/search`\
**File**: `frontend/src/pages/SearchPageSimple.tsx`\
**Category**: Optional (requires ES)

### Purpose

Elasticsearch search interface with:

- Full-text search
- Faceted filtering
- Result cards with images
- Pagination

### When to Use

- Demos requiring product/content search
- Showcasing Elasticsearch capabilities
- Combining search with chat (hybrid demos)

### Requirements

- `ELASTIC_CLOUD_ID` or `ELASTICSEARCH_URL` in `.env`
- `ELASTIC_API_KEY` with read access
- `SEARCH_INDEX` pointing to your index

### Configuration

Edit `frontend/src/config/searchConfig.ts`:

```typescript
export const searchConfig: SearchConfig = {
  index: "products",
  fields: {
    search: [
      { field: "title", boost: 3 },
      { field: "description", boost: 1 },
    ],
  },
  display: {
    title: "title",
    description: "description",
    image: "image_url",
    price: "price",
  },
  facets: [
    { field: "category", label: "Category", size: 10 },
    { field: "brand", label: "Brand", size: 10 },
  ],
}
```

______________________________________________________________________

## Adding New Pages

To add a new page to the demo:

### 1. Create the Page Component

```tsx
// frontend/src/pages/MyNewPage.tsx
import { EuiPageTemplate, EuiTitle } from '@elastic/eui'
import { AppHeader } from '../components/layout/AppHeader'

export function MyNewPage() {
  return (
    <>
      <AppHeader />
      <EuiPageTemplate>
        <EuiPageTemplate.Section>
          <EuiTitle><h1>My New Page</h1></EuiTitle>
          {/* Your content */}
        </EuiPageTemplate.Section>
      </EuiPageTemplate>
    </>
  )
}
```

### 2. Add the Route

Edit `frontend/src/App.tsx`:

```tsx
import { MyNewPage } from './pages/MyNewPage'

// In the Routes section:
<Route path="/my-page" element={<MyNewPage />} />
```

### 3. Add to Navigation

Edit `frontend/src/components/layout/navigationConfig.ts`:

```typescript
export const NAV_ITEMS: NavItem[] = [
  // ... existing items
  {
    path: '/my-page',
    label: 'My Page',
    icon: 'document',  // EUI icon name
    description: 'What this page does',
    category: 'demo',  // 'demo' | 'tools' | 'advanced'
  },
]
```

### 4. (Optional) Add to Welcome Page

Edit the `FEATURES` array in `WelcomePage.tsx` to show it on the landing page.

______________________________________________________________________

## Page Categories

Pages are organized into three categories:

### Demo Building (`demo`)

Features for creating customer presentations:

- Chat, Branded Demo, Brand Editor

### Development Tools (`tools`)

Features for debugging and exploration:

- Audit, MCP Explorer

### Advanced (`advanced`)

Features requiring additional setup:

- A2A Chat, Search (when ES not configured)

______________________________________________________________________

## Navigation System

Navigation is centralized in `frontend/src/components/layout/navigationConfig.ts`.

Two header variants are available:

- `AppHeader.tsx` - Full navigation with all pages
- `AppHeaderSimple.tsx` - Minimal header for focused demos

To use the simple header:

```tsx
import { AppHeaderSimple } from '../components/layout/AppHeaderSimple'

function MyPage() {
  return (
    <>
      <AppHeaderSimple title="My Demo" />
      {/* Content */}
    </>
  )
}
```
