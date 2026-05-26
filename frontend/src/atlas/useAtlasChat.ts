/**
 * useAtlasChat — chat state + memory event capture for the Atlas demo.
 */

import { useCallback, useRef, useState } from 'react'
import {
  ChatHistoryMessage,
  MemoryHit,
  MemoryType,
  streamAtlasChat,
} from './api'

export interface AtlasMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  isComplete: boolean
  toolCalls: AtlasToolCall[]
  recalled: MemoryHit[]
  writes: AtlasMemoryWrite[]
}

export interface AtlasToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
  result?: unknown
}

export interface AtlasMemoryWrite {
  id: string
  memory_type: MemoryType
  text: string
  fact_type?: string
}

export interface UseAtlasChatOptions {
  userId: string
  sessionId: string
}

interface RawEvent {
  event: string
  [key: string]: unknown
}

export function useAtlasChat({ userId, sessionId }: UseAtlasChatOptions) {
  const [messages, setMessages] = useState<AtlasMessage[]>([])
  const [isStreaming, setStreaming] = useState(false)
  const [isConsolidating, setConsolidating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setMessages([])
    setError(null)
    setStreaming(false)
    setConsolidating(false)
  }, [])

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return
      const ctrl = new AbortController()
      abortRef.current?.abort()
      abortRef.current = ctrl

      const userMsg: AtlasMessage = {
        id: `u-${Date.now()}`,
        role: 'user',
        content: text,
        isComplete: true,
        toolCalls: [],
        recalled: [],
        writes: [],
      }
      const assistantId = `a-${Date.now()}`
      const assistantMsg: AtlasMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        isComplete: false,
        toolCalls: [],
        recalled: [],
        writes: [],
      }
      const history: ChatHistoryMessage[] = messages
        .filter(m => m.isComplete)
        .map(m => ({ role: m.role, content: m.content }))

      setError(null)
      setMessages(prev => [...prev, userMsg, assistantMsg])
      setStreaming(true)

      const updateAssistant = (
        mut: (m: AtlasMessage) => AtlasMessage,
      ) => {
        setMessages(prev =>
          prev.map(m => (m.id === assistantId ? mut(m) : m)),
        )
      }

      try {
        await streamAtlasChat(
          { user_id: userId, session_id: sessionId, message: text, history },
          (raw: RawEvent) => {
            switch (raw.event) {
              case 'text_chunk': {
                const t = (raw.text as string) ?? ''
                updateAssistant(m => ({ ...m, content: m.content + t }))
                break
              }
              case 'tool_call': {
                const tc: AtlasToolCall = {
                  id: (raw.id as string) ?? '',
                  name: (raw.name as string) ?? '',
                  arguments:
                    (raw.arguments as Record<string, unknown>) ?? {},
                }
                updateAssistant(m => ({
                  ...m,
                  toolCalls: [...m.toolCalls, tc],
                }))
                break
              }
              case 'tool_result': {
                const id = raw.id as string
                const result = raw.result
                updateAssistant(m => ({
                  ...m,
                  toolCalls: m.toolCalls.map(tc =>
                    tc.id === id ? { ...tc, result } : tc,
                  ),
                  recalled:
                    raw.name === 'recall_memory' &&
                    result &&
                    typeof result === 'object' &&
                    'hits' in (result as Record<string, unknown>)
                      ? [
                          ...m.recalled,
                          ...(((result as { hits: MemoryHit[] }).hits) || []),
                        ]
                      : m.recalled,
                }))
                break
              }
              case 'memory_write': {
                const w: AtlasMemoryWrite = {
                  id: (raw.id as string) ?? '',
                  memory_type: (raw.memory_type as MemoryType) ?? 'episodic',
                  text: (raw.text as string) ?? '',
                }
                updateAssistant(m => ({
                  ...m,
                  writes: [...m.writes, w],
                }))
                break
              }
              case 'done': {
                updateAssistant(m => ({ ...m, isComplete: true }))
                break
              }
              case 'consolidation_start': {
                setConsolidating(true)
                break
              }
              case 'consolidation_fact': {
                // Add consolidated fact to the assistant's writes so it
                // appears highlighted green in the memory inspector.
                const w: AtlasMemoryWrite = {
                  id: (raw.id as string) ?? '',
                  memory_type: (raw.memory_type as MemoryType) ?? 'semantic',
                  text: (raw.text as string) ?? '',
                  fact_type: raw.fact_type as string | undefined,
                }
                updateAssistant(m => ({ ...m, writes: [...m.writes, w] }))
                break
              }
              case 'consolidation_update':
              case 'consolidation_done': {
                setConsolidating(false)
                break
              }
              case 'error': {
                setError((raw.message as string) || 'Atlas error')
                updateAssistant(m => ({ ...m, isComplete: true }))
                break
              }
            }
          },
          ctrl.signal,
        )
      } catch (e) {
        if ((e as Error).name === 'AbortError') return
        setError((e as Error).message)
        updateAssistant(m => ({ ...m, isComplete: true }))
      } finally {
        setStreaming(false)
      }
    },
    [isStreaming, messages, sessionId, userId],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setStreaming(false)
  }, [])

  return { messages, isStreaming, isConsolidating, error, send, stop, reset }
}
