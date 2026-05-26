/**
 * Browser Tool Types
 *
 * Generic types for the Agent Builder browser tools integration.
 * Browser tools let the agent emit structured UI actions that the
 * frontend dispatches to registered handler functions.
 *
 * The template provides the FRAMEWORK (types, dispatch, wiring).
 * Demos register their own tool schemas and handlers.
 *
 * @example
 * // Registering handlers in a page component:
 * const handlers: BrowserToolHandlerMap = {
 *   'browser.show_results': (params) => setResults(params as ResultData),
 *   'browser.update_cart': (params) => addToCart(params as CartItem),
 * }
 * <ChatContainer onBrowserToolCall={(inv) => dispatchBrowserTool(inv, handlers)} />
 */

// ---------------------------------------------------------------------------
// Tool definition (sent to Agent Builder in the chat request)
// ---------------------------------------------------------------------------

/**
 * A browser tool definition for the Agent Builder API.
 * Mirrors the JSON Schema format expected by the chat endpoint.
 */
export interface BrowserApiTool {
  name: string
  description: string
  parameters: {
    type: 'object'
    properties: Record<string, unknown>
    required?: string[]
  }
}

// ---------------------------------------------------------------------------
// Invocation (received from Agent Builder SSE stream)
// ---------------------------------------------------------------------------

/**
 * A browser tool invocation received from the Agent Builder SSE stream.
 * Built by useAgentChat when a tool_call event has a browser-prefixed ID.
 */
export interface BrowserToolInvocation {
  /** Normalized tool ID in dotted form (e.g. "browser.show_results") */
  toolId: string
  /** Original tool call ID from Agent Builder (for correlation) */
  toolCallId?: string
  /** Parsed parameters from the agent */
  payload: unknown
  /** When the invocation was received */
  timestamp: number
}

// ---------------------------------------------------------------------------
// Handler types
// ---------------------------------------------------------------------------

/**
 * A function that handles a browser tool invocation.
 *
 * @param params - The tool parameters (payload from the agent)
 * @param invocation - The full invocation object (for toolCallId, timestamp)
 * @param context - Optional shared context (e.g. current cart items for dedup)
 */
export type BrowserToolHandler = (
  params: unknown,
  invocation: BrowserToolInvocation,
  context?: Record<string, unknown>,
) => void | unknown | Promise<void | unknown>

/** Map of tool IDs to handler functions */
export type BrowserToolHandlerMap = Record<string, BrowserToolHandler>

// ---------------------------------------------------------------------------
// Dispatch options
// ---------------------------------------------------------------------------

/** Options for the dispatch function */
export interface DispatchOptions {
  /** Shared context passed to all handlers (e.g. { currentCart: [...] }) */
  context?: Record<string, unknown>
  /** Known tool IDs — if set, unknown tools are logged as warnings */
  knownToolIds?: Set<string>
  /** Enable dispatch logging (default: true) */
  log?: boolean
  /** Custom payload summarizer for logging. Receives (toolId, payload) and returns summary fields. */
  summarize?: (toolId: string, payload: unknown) => Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Logging
// ---------------------------------------------------------------------------

/** A single entry in the dispatch log ring buffer */
export interface BrowserToolLogEntry {
  toolId: string
  normalizedId: string
  timestamp: number
  success: boolean
  error?: string
  /** Summary fields for debugging (not the full payload) */
  summary: Record<string, unknown>
}
