/**
 * LLM Proxy API Service
 * 
 * Handles communication with the backend A2A chat endpoint.
 * Supports streaming responses, function calling, and error handling.
 * 
 * PATTERNS FROM HIVE-MIND DOCUMENTATION:
 * - Use fetch with response.body.getReader() for streaming
 * - Buffer incomplete lines for proper SSE parsing
 * - Normalize event types
 * - Support AbortController for cancellation
 */

// Event types from A2A chat endpoint
export type A2AEventType =
  | 'function_call'         // Server-side function (Agent Builder)
  | 'client_function_call'  // Client-side function (executed in browser)
  | 'text_chunk'
  | 'agent_text_chunk'
  | 'agent_reasoning'
  | 'agent_tool_call'
  | 'agent_tool_status'
  | 'agent_tool_result'
  | 'error'

export interface A2AEvent {
  type: A2AEventType
  data: Record<string, unknown>
}

// Client function definition type (for client-side functions)
export interface ClientFunctionDef {
  name: string
  description: string
  parameters: Record<string, unknown>
}

/**
 * Normalize raw event data from A2A chat endpoint.
 */
function normalizeA2AEvent(rawData: Record<string, unknown>): A2AEvent {
  const eventType = rawData.event as A2AEventType
  const payload = rawData.data || rawData

  return {
    type: eventType || 'text_chunk',
    data: payload as Record<string, unknown>,
  }
}

/**
 * Stream messages from the A2A chat endpoint.
 * 
 * @param message - User message to send
 * @param conversationId - Optional conversation ID for multi-turn
 * @param onEvent - Callback for each normalized event
 * @param signal - AbortSignal for cancellation
 * @param systemPrompt - Optional custom system instructions
 * @param clientFunctions - Optional client-side functions (executed in browser)
 * @param endpoint - Optional API endpoint (default: /api/a2a/chat)
 */
export async function streamA2AChat(
  message: string,
  conversationId: string | undefined,
  onEvent: (event: A2AEvent) => void,
  signal?: AbortSignal,
  systemPrompt?: string,
  clientFunctions?: ClientFunctionDef[],
  endpoint: string = '/api/a2a/chat'
): Promise<void> {
  // Build request body, only including optional fields if they have values
  const requestBody: Record<string, unknown> = {
    message,
    conversation_id: conversationId,
  }
  
  if (systemPrompt && systemPrompt.trim()) {
    requestBody.system_prompt = systemPrompt.trim()
  }
  
  if (clientFunctions && clientFunctions.length > 0) {
    requestBody.client_functions = clientFunctions
  }
  
  // Use relative path - Vite proxy handles routing to backend
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
    signal,
  })

  if (!response.ok) {
    // Try to parse structured error response
    const errorText = await response.text()
    let errorDetail: { error_code?: string; message?: string; setup_hint?: string } = {}
    
    try {
      const parsed = JSON.parse(errorText)
      if (parsed.detail && typeof parsed.detail === 'object') {
        errorDetail = parsed.detail
      } else if (parsed.detail && typeof parsed.detail === 'string') {
        errorDetail = { message: parsed.detail }
      }
    } catch {
      errorDetail = { message: errorText }
    }
    
    // Create error with structured data attached
    const error = new Error(errorDetail.message || `API error: ${response.status}`) as Error & {
      errorCode?: string
      setupHint?: string
      statusCode?: number
    }
    error.errorCode = errorDetail.error_code
    error.setupHint = errorDetail.setup_hint
    error.statusCode = response.status
    throw error
  }

  if (!response.body) {
    throw new Error('No response body - streaming not supported')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    // Decode chunk and add to buffer
    buffer += decoder.decode(value, { stream: true })
    
    // Process complete lines
    const lines = buffer.split('\n')
    buffer = lines.pop() || '' // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        // SSE data line - parse and emit event
        try {
          const data = JSON.parse(line.slice(6))
          onEvent(normalizeA2AEvent(data))
        } catch {
          console.warn('Failed to parse SSE data:', line)
        }
      }
      // Ignore empty lines (SSE delimiters) and comments (keepalives)
    }
  }
}

/**
 * Fetch available agents and their function definitions.
 */
export async function fetchAgents(): Promise<{
  agents: Array<{
    id: string
    name: string
    description: string
    skills: Array<{
      id: string
      name: string
      description: string
    }>
  }>
  functions: Array<{
    name: string
    description: string
    parameters: Record<string, unknown>
  }>
}> {
  const response = await fetch('/api/a2a/agents')

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Failed to fetch agents: ${response.status} - ${errorText}`)
  }

  return response.json()
}

// Extended error type with structured data from backend
export interface A2AError extends Error {
  errorCode?: string
  setupHint?: string
  statusCode?: number
}

/**
 * User-friendly error messages for common failures.
 * Returns an object with message and optional setup hint.
 */
export function getA2AErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    const a2aError = error as A2AError
    
    // If we have a structured error code, use it for better messages
    if (a2aError.errorCode) {
      switch (a2aError.errorCode) {
        case 'LLM_PROXY_NOT_CONFIGURED':
          return 'A2A is not configured. Please set up LLM proxy in backend/.env'
        case 'LLM_PROXY_AUTH_FAILED':
          return 'LLM proxy authentication failed. Your API key may be expired or invalid.'
        case 'LLM_PROXY_FORBIDDEN':
          return 'Access denied. Your API key may not have the required permissions.'
        case 'LLM_PROXY_RATE_LIMITED':
          return 'Too many requests. Please wait a moment and try again.'
        case 'LLM_PROXY_UNREACHABLE':
          return 'Cannot connect to LLM proxy. Check your network connection.'
        case 'LLM_PROXY_TIMEOUT':
          return 'LLM proxy is taking too long to respond. Please try again.'
        case 'LLM_PROXY_ERROR':
          return a2aError.message || 'LLM proxy error. Please try again.'
      }
    }
    
    const msg = error.message
    
    // Network errors
    if (error.name === 'TypeError' && msg.includes('fetch')) {
      return 'Unable to connect. Please check your internet connection.'
    }
    
    // Timeout
    if (error.name === 'AbortError') {
      return 'Request was cancelled.'
    }
    
    // Fallback API errors (for backwards compatibility)
    if (msg.includes('401')) {
      return 'Authentication failed. Please check LLM proxy API key.'
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

/**
 * Get detailed error info including setup hints.
 */
export function getA2AErrorDetails(error: unknown): {
  message: string
  errorCode?: string
  setupHint?: string
  isConfigError: boolean
} {
  const message = getA2AErrorMessage(error)
  
  if (error instanceof Error) {
    const a2aError = error as A2AError
    const isConfigError = !!(a2aError.errorCode?.startsWith('LLM_PROXY_') && 
      ['LLM_PROXY_NOT_CONFIGURED', 'LLM_PROXY_AUTH_FAILED', 'LLM_PROXY_FORBIDDEN'].includes(a2aError.errorCode || ''))
    
    return {
      message,
      errorCode: a2aError.errorCode,
      setupHint: a2aError.setupHint,
      isConfigError,
    }
  }
  
  return { message, isConfigError: false }
}


// =============================================================================
// A2A Health Check
// =============================================================================

export interface A2AHealthStatus {
  status: 'healthy' | 'not_configured' | 'unhealthy'
  llm_proxy_configured: boolean
  llm_proxy_url?: string | null
  llm_proxy_model?: string
  setup_hint?: string
  setup_steps?: string[]
  error?: string
  error_code?: string
  connectivity_tested?: boolean
  connectivity_ok?: boolean
}

/**
 * Check A2A health status.
 * 
 * Returns information about whether LLM proxy is configured and accessible.
 * Use this before showing the A2A chat interface.
 */
export async function checkA2AHealth(): Promise<A2AHealthStatus> {
  try {
    const response = await fetch('/api/a2a/health')
    
    if (!response.ok) {
      return {
        status: 'unhealthy',
        llm_proxy_configured: false,
        error: `Health check failed: ${response.status}`,
      }
    }
    
    return response.json()
  } catch (error) {
    return {
      status: 'unhealthy',
      llm_proxy_configured: false,
      error: error instanceof Error ? error.message : 'Failed to check health',
    }
  }
}

/**
 * Test A2A connectivity (slower but more thorough).
 * 
 * Actually makes a request to the LLM proxy to verify it's working.
 */
export async function testA2AConnectivity(): Promise<A2AHealthStatus> {
  try {
    const response = await fetch('/api/a2a/health/test')
    
    if (!response.ok) {
      return {
        status: 'unhealthy',
        llm_proxy_configured: false,
        error: `Connectivity test failed: ${response.status}`,
      }
    }
    
    return response.json()
  } catch (error) {
    return {
      status: 'unhealthy',
      llm_proxy_configured: false,
      error: error instanceof Error ? error.message : 'Failed to test connectivity',
    }
  }
}

