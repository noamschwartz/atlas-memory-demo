/**
 * Audit API Service
 * 
 * Fetches conversation history from the backend audit API.
 * The backend proxies requests to Elastic Agent Builder's conversation endpoints.
 * 
 * See: hive-mind/patterns/agent-builder/CONVERSATION_HISTORY_AUDIT.md
 */

const API_BASE = '/api/audit'

// ============================================================================
// Types
// ============================================================================

/**
 * User info attached to conversations
 */
export interface ConversationUser {
  id?: string
  username: string
}

/**
 * Conversation summary (from list endpoint)
 */
export interface ConversationSummary {
  id: string
  agent_id: string
  user?: ConversationUser
  title?: string
  created_at: string
  updated_at?: string
}

/**
 * Full conversation detail including rounds and steps
 */
export interface ConversationDetail extends ConversationSummary {
  rounds: ConversationRound[]
}

/**
 * A single conversation round (user message + assistant response)
 */
export interface ConversationRound {
  id: string
  input: {
    message: string
    attachments?: unknown[]
  }
  steps: ConversationStep[]
  response?: {
    message: string
  }
  started_at?: string
  time_to_first_token?: number  // milliseconds
  time_to_last_token?: number   // milliseconds
}

/**
 * Step in a conversation round - either reasoning or tool call
 */
export type ConversationStep = ReasoningStep | ToolCallStep

/**
 * Agent reasoning/thinking step
 */
export interface ReasoningStep {
  type: 'reasoning'
  reasoning: string
}

/**
 * Tool invocation step with parameters and results
 */
export interface ToolCallStep {
  type: 'tool_call'
  tool_call_id: string
  tool_id: string
  params: Record<string, unknown>
  progression?: { message: string }[]
  results?: ToolResult[]
}

/**
 * Result from a tool call
 */
export interface ToolResult {
  tool_result_id: string
  type: string
  data: Record<string, unknown>
}

/**
 * Agent summary for filter dropdown
 */
export interface AgentSummary {
  id: string
  name: string
  description?: string
}

// ============================================================================
// Type Guards
// ============================================================================

export function isReasoningStep(step: ConversationStep): step is ReasoningStep {
  return step.type === 'reasoning'
}

export function isToolCallStep(step: ConversationStep): step is ToolCallStep {
  return step.type === 'tool_call'
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch conversation list from audit API
 */
export async function listConversations(
  agentId?: string
): Promise<ConversationSummary[]> {
  const params = new URLSearchParams()
  if (agentId) params.set('agent_id', agentId)
  
  const url = `${API_BASE}/conversations${params.toString() ? `?${params}` : ''}`
  const response = await fetch(url)
  
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to fetch conversations: ${error}`)
  }
  
  const data = await response.json()
  // API returns { results: [...] } 
  return data.results || []
}

/**
 * Fetch full conversation detail
 */
export async function getConversation(
  conversationId: string
): Promise<ConversationDetail> {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}`)
  
  if (response.status === 404) {
    throw new Error('Conversation not found')
  }
  
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to fetch conversation: ${error}`)
  }
  
  return response.json()
}

/**
 * Fetch list of available agents for filtering
 */
export async function listAgents(): Promise<AgentSummary[]> {
  const response = await fetch(`${API_BASE}/agents`)
  
  if (!response.ok) {
    // Non-critical - return empty array if agents list fails
    console.warn('Failed to fetch agents list')
    return []
  }
  
  const data = await response.json()
  return data.results || []
}
