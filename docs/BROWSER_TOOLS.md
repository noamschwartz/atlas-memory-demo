# Browser Tools Framework

Browser tools allow Agent Builder agents to emit structured UI actions that
the frontend dispatches to registered handler functions. This enables agents
to control page-level state (e.g. showing search results, updating a cart,
displaying a comparison table) without tight coupling between the agent and
the UI.

## Architecture

```
Agent Builder → SSE stream → useAgentChat → onBrowserToolCall → dispatchBrowserTool → handler
```

1. **Define tools** — Create `BrowserApiTool` JSON schemas describing what the agent can call
2. **Register handlers** — Build a `BrowserToolHandlerMap` mapping tool IDs to functions
3. **Wire up** — Pass tools and handler callback to `ChatContainer`
4. **Dispatch** — When the agent calls a tool, the framework normalizes the ID and dispatches

## Quick Start

### 1. Define tool schemas

```typescript
// config/myDemoTools.ts
import type { BrowserApiTool } from '../types/browserTools'

export const MY_TOOLS: BrowserApiTool[] = [
  {
    name: 'browser.show_results',
    description: 'Display search results in the side panel',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'The search query' },
        results: { type: 'array', items: { type: 'object' } },
      },
      required: ['query', 'results'],
    },
  },
]
```

### 2. Register handlers

```typescript
// In your page component
import { dispatchBrowserTool } from '../config/browserToolDispatch'
import type { BrowserToolHandlerMap, BrowserToolInvocation } from '../types/browserTools'

const handlers: BrowserToolHandlerMap = {
  'browser.show_results': (params) => {
    const { results } = params as { results: unknown[] }
    setSearchResults(results)
  },
}

const handleBrowserTool = (invocation: BrowserToolInvocation) => {
  dispatchBrowserTool(invocation, handlers)
}
```

### 3. Wire to ChatContainer

```tsx
<ChatContainer
  browserApiTools={MY_TOOLS}
  onBrowserToolCall={handleBrowserTool}
  title="My Assistant"
/>
```

## Tool ID Normalization

Agent Builder may send tool IDs in different formats. The framework normalizes them:

| Agent sends | Normalized to |
|---|---|
| `browser_show_results` | `browser.show_results` |
| `browser.show_results` | `browser.show_results` |
| `browser_browser_foo` | `browser.foo` |

## Parameter Extraction

Some Agent Builder configurations wrap parameters in a `kwargs` key.
`getBrowserToolParams()` automatically unwraps this:

```typescript
// Agent sends: { kwargs: { query: "shoes" } }
// Handler receives: { query: "shoes" }
```

## Error Containment

Handler errors are caught and logged — they never crash the chat:

```typescript
const handlers: BrowserToolHandlerMap = {
  'browser.risky_action': (params) => {
    throw new Error('Something went wrong')
    // Error is logged, chat continues normally
  },
}
```

## Debugging

Access the dispatch log from the browser console:

```javascript
window.__browserToolLog()
```

## Strict Mode

Set `VITE_STRICT_BROWSER_TOOLS=true` in your `.env` to enable stricter
validation of browser tool calls (useful during development).

In strict mode, if the agent calls a browser-prefixed tool and no handler
is registered for it, the dispatcher logs a console error and records a
failure in the dispatch log. Without strict mode, unhandled tools silently
return `false`.
