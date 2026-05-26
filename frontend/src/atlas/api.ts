/**
 * Atlas API client — chat SSE + memory CRUD.
 */

const API_BASE = ''

export type MemoryType = 'episodic' | 'semantic' | 'procedural'

export interface AtlasEvent {
  event: string
  [key: string]: unknown
}

export interface MemoryHit {
  id: string
  index: string
  memory_type: MemoryType
  score: number
  rank: number
  source: Record<string, unknown>
}

export interface MemoryItem {
  id: string
  source: Record<string, unknown>
}

export interface ChatHistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  user_id: string
  session_id: string
  message: string
  history: ChatHistoryMessage[]
}

/** Stream Atlas chat SSE events. Calls onEvent for each parsed payload. */
export async function streamAtlasChat(
  req: ChatRequest,
  onEvent: (ev: AtlasEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/atlas/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal,
  })
  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => '')
    throw new Error(`atlas chat failed: ${resp.status} ${text}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE messages are separated by blank lines.
    let nl = buffer.indexOf('\n\n')
    while (nl !== -1) {
      const raw = buffer.slice(0, nl).trim()
      buffer = buffer.slice(nl + 2)
      nl = buffer.indexOf('\n\n')

      const line = raw.startsWith('data:') ? raw.slice(5).trim() : raw
      if (!line) continue
      try {
        onEvent(JSON.parse(line) as AtlasEvent)
      } catch (err) {
        console.warn('atlas SSE parse error:', err, line)
      }
    }
  }
}

export async function recallMemory(
  user_id: string,
  query: string,
  k = 10,
  memory_types?: MemoryType[],
): Promise<MemoryHit[]> {
  const resp = await fetch(`${API_BASE}/api/memory/recall`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id, query, k, memory_types }),
  })
  if (!resp.ok) throw new Error(`recall failed: ${resp.status}`)
  const data = await resp.json()
  return data.hits ?? []
}

export async function listMemories(
  user_id: string,
  memory_type: MemoryType,
  limit = 50,
): Promise<MemoryItem[]> {
  const resp = await fetch(
    `${API_BASE}/api/memory/list?user_id=${encodeURIComponent(user_id)}` +
      `&memory_type=${memory_type}&limit=${limit}`,
  )
  if (!resp.ok) throw new Error(`list failed: ${resp.status}`)
  const data = await resp.json()
  return data.items ?? []
}

export interface ConsolidateResponse {
  candidates: Array<{
    text: string
    fact_type: string
    confidence: number
    supporting_episode_ids: string[]
  }>
  created: Array<{ id: string; memory_type: MemoryType; fact: unknown }>
  dry_run: boolean
  error?: string
}

export async function consolidateMemory(
  user_id: string,
  opts: { dry_run?: boolean; lookback?: number } = {},
): Promise<ConsolidateResponse> {
  const resp = await fetch(`${API_BASE}/api/memory/consolidate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id,
      dry_run: opts.dry_run ?? false,
      lookback: opts.lookback ?? 30,
    }),
  })
  if (!resp.ok) throw new Error(`consolidate failed: ${resp.status}`)
  return resp.json()
}

export async function memoryHealth(): Promise<{
  counts: Record<MemoryType, number>
}> {
  const resp = await fetch(`${API_BASE}/api/memory/health`)
  if (!resp.ok) throw new Error(`health failed: ${resp.status}`)
  return resp.json()
}
