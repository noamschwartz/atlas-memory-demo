/**
 * Agent Builder API Service
 * 
 * Handles SSE streaming from the backend proxy to Agent Builder.
 * 
 * PATTERNS FROM HIVE-MIND DOCUMENTATION:
 * - Use fetch with response.body.getReader() for streaming
 * - Buffer incomplete lines for proper SSE parsing
 * - Normalize inconsistent event types from Agent Builder
 * - Support AbortController for cancellation
 */

import type { BrowserApiTool } from '../types/browserTools'

// Event types from Agent Builder
export type EventType =
  | 'conversation_created'
  | 'reasoning'
  | 'tool_call'
  | 'tool_result'
  | 'text_chunk'
  | 'message_complete'
  | 'error'

export interface NormalizedEvent {
  type: EventType
  data: Record<string, unknown>
  conversationId?: string
}

/**
 * Normalize raw event data from Agent Builder.
 * 
 * Agent Builder can return:
 * - Nested data: { data: { data: ... } }
 * - Inconsistent event names: 'message_chunk' vs 'text_chunk'
 * - Missing event types that need inference from payload
 */
function normalizeEvent(
  explicitType: string | null,
  rawData: Record<string, unknown>
): NormalizedEvent {
  // 1. Unwrap nested data (Agent Builder quirk)
  let payload = (rawData.data || rawData) as Record<string, unknown>
  if (payload.data && typeof payload.data === 'object') {
    payload = payload.data as Record<string, unknown>
  }

  // 2. Map known event names to our internal types
  const typeMap: Record<string, EventType> = {
    'message_chunk': 'text_chunk',
    'conversation_updated': 'conversation_created',
    'conversation_id_set': 'conversation_created',
  }

  let type: EventType = 'text_chunk'
  const rawType = explicitType || (rawData.event as string)

  if (rawType && typeMap[rawType]) {
    type = typeMap[rawType]
  } else if (rawType) {
    type = rawType as EventType
  } else {
    // 3. Infer type from payload structure
    if (payload.reasoning) type = 'reasoning'
    else if (payload.tool_call_id && !payload.result) type = 'tool_call'
    else if (payload.result || payload.output) type = 'tool_result'
    else if (payload.conversation_id && payload.title) type = 'conversation_created'
    else if (payload.text_chunk || payload.text) type = 'text_chunk'
    else if (payload.message_content) type = 'message_complete'
  }

  return {
    type,
    data: payload,
    conversationId: payload.conversation_id as string | undefined,
  }
}

/**
 * Stream messages from the Agent Builder via backend proxy.
 * 
 * Note: In Vite, the /api path is proxied to the backend in vite.config.ts
 * So we just use relative paths here.
 * 
 * @param message - User message to send
 * @param conversationId - Optional conversation ID for multi-turn
 * @param onEvent - Callback for each normalized event
 * @param signal - AbortSignal for cancellation
 * @param browserApiTools - Optional browser tool definitions to register with Agent Builder
 * @param profileContext - Optional rich profile context injected on first message
 * @param modeContext - Optional mode context prefix for multi-mode agents
 * @param agentId - Optional agent ID override for mode-specific routing
 */
export async function streamAgentMessage(
  message: string,
  conversationId: string | undefined,
  onEvent: (event: NormalizedEvent) => void,
  signal?: AbortSignal,
  browserApiTools?: BrowserApiTool[],
  profileContext?: string | null,
  modeContext?: string | null,
  agentId?: string | null,
): Promise<void> {
  // Use relative path - Vite proxy handles routing to backend
  const response = await fetch('/api/agent/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      input: message,
      conversation_id: conversationId,
      ...(browserApiTools?.length ? { browser_api_tools: browserApiTools } : {}),
      ...(profileContext ? { profile_context: profileContext } : {}),
      ...(modeContext ? { mode_context: modeContext } : {}),
      ...(agentId ? { agent_id: agentId } : {}),
    }),
    signal,
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`API error: ${response.status} - ${errorText}`)
  }

  if (!response.body) {
    throw new Error('No response body - streaming not supported')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEventType: string | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    // Decode chunk and add to buffer
    buffer += decoder.decode(value, { stream: true })
    
    // Process complete lines
    const lines = buffer.split('\n')
    buffer = lines.pop() || '' // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        // SSE event type line
        currentEventType = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        // SSE data line - parse and emit event
        try {
          const data = JSON.parse(line.slice(6))
          onEvent(normalizeEvent(currentEventType, data))
        } catch {
          console.warn('Failed to parse SSE data:', line)
        }
        currentEventType = null
      }
      // Ignore empty lines (SSE delimiters) and comments (keepalives)
    }
  }
}

/**
 * User-friendly error messages for common failures.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    const msg = error.message
    
    // Network errors
    if (error.name === 'TypeError' && msg.includes('fetch')) {
      return 'Unable to connect. Please check your internet connection.'
    }
    
    // Timeout
    if (error.name === 'AbortError') {
      return 'Request was cancelled.'
    }
    
    // API errors
    if (msg.includes('401')) {
      return 'Authentication failed. Please check credentials.'
    }
    if (msg.includes('429')) {
      return 'Too many requests. Please wait a moment.'
    }
    if (msg.includes('500') || msg.includes('502')) {
      return 'Server error. Please try again.'
    }
    
    return msg
  }
  
  return 'Something went wrong. Please try again.'
}
