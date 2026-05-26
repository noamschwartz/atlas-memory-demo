/**
 * Lumio Support — Agent Memory Demo
 * Split layout: streaming chat (left) + live memory inspector (right).
 * Full-viewport height, no overflow; markdown rendered; UTF-8 clean.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  EuiButton,
  EuiButtonEmpty,
  EuiFieldText,
  EuiFlexGroup,
  EuiFlexItem,
  EuiHealth,
  EuiPanel,
  EuiSelect,
  EuiText,
  EuiTitle,
} from '@elastic/eui'
import { MemoryInspector } from './MemoryInspector'
import { useAtlasChat } from './useAtlasChat'
import { MarkdownContent } from '../components/chat/MarkdownContent'

const USERS = [
  { value: 'sarah', text: 'Sarah (Hub v2 owner)' },
  { value: 'james', text: 'James (Hub v1 — considering upgrade)' },
  { value: 'priya', text: 'Priya (power user, architect, Bengaluru)' },
]

const SUGGESTED_PROMPTS = [
  "My hub keeps disconnecting — this is happening again",
  "My new smart bulbs aren't showing colors, only white",
  "What firmware version should I be on?",
  "Is it worth upgrading to Hub v2?",
]

// App header is position: fixed at 56px per project convention.
const HEADER_H = 56

export function AtlasMemoryPage() {
  const [userId, setUserId] = useState('sarah')
  const [sessionId] = useState(() => `s-${Date.now()}`)
  const [draft, setDraft] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  const { messages, isStreaming, isConsolidating, error, send, reset } = useAtlasChat({ userId, sessionId })

  useEffect(() => {
    reset()
    setRefreshKey(k => k + 1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  useEffect(() => {
    if (!isStreaming) setRefreshKey(k => k + 1)
  }, [isStreaming])

  const lastAssistant = useMemo(
    () => [...messages].reverse().find(m => m.role === 'assistant'),
    [messages],
  )
  const recalledIds = useMemo(
    () => (lastAssistant?.recalled ?? []).map(h => h.id),
    [lastAssistant],
  )
  const writtenIds = useMemo(
    () =>
      messages
        .filter(m => m.role === 'assistant')
        .flatMap(m => m.writes.map(w => w.id))
        .concat(messages.filter(m => m.role === 'user').map(m => m.id)),
    [messages],
  )

  const handleSend = () => {
    const t = draft.trim()
    if (!t) return
    setDraft('')
    void send(t)
  }

  const transcriptRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  return (
    <div style={{
      position: 'fixed',
      top: HEADER_H,
      left: 0,
      right: 0,
      bottom: 0,
      display: 'flex',
      flexDirection: 'column',
      padding: '16px 24px 12px',
      overflow: 'hidden',
      boxSizing: 'border-box',
    }}>
      {/* ── Page header ──────────────────────────────────── */}
      <div style={{ flexShrink: 0, marginBottom: 12 }}>
        <EuiFlexGroup alignItems="center" justifyContent="spaceBetween" gutterSize="m" responsive={false}>
          <EuiFlexItem>
            <EuiTitle size="s"><h1>Lumio Support — Agent Memory on Elasticsearch</h1></EuiTitle>
            <EuiText size="xs" color="subdued">
              Customer support agent with per-customer memory in Elasticsearch.
              Hybrid recall (BM25 + Jina v5) over customer memory + shared knowledge base.
              Switch customers to see per-user isolation.
            </EuiText>
          </EuiFlexItem>
          <EuiFlexItem grow={false} style={{ minWidth: 280 }}>
            <EuiSelect
              prepend="Customer"
              options={USERS}
              value={userId}
              onChange={e => setUserId(e.target.value)}
            />
          </EuiFlexItem>
        </EuiFlexGroup>
      </div>

      {/* ── Main split layout ─────────────────────────────── */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 12 }}>

        {/* ── Chat panel ──────────────────────────────────── */}
        <div style={{ flex: 2, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <EuiPanel hasBorder paddingSize="s" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>

            {/* Transcript — scrollable */}
            <div ref={transcriptRef} style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
              {messages.length === 0 && (
                <div style={{ padding: '32px 16px', textAlign: 'center' }}>
                  <EuiText size="s" color="subdued">
                    <p style={{ marginBottom: 16 }}>Select a suggested question or type your own.</p>
                  </EuiText>
                  <EuiFlexGroup gutterSize="s" wrap justifyContent="center">
                    {SUGGESTED_PROMPTS.map(p => (
                      <EuiFlexItem key={p} grow={false}>
                        <EuiButtonEmpty
                          size="s"
                          onClick={() => { setDraft(p) }}
                          style={{
                            border: '1px solid var(--euiColorLightShade)',
                            borderRadius: 4,
                            padding: '4px 10px',
                          }}
                        >
                          {p}
                        </EuiButtonEmpty>
                      </EuiFlexItem>
                    ))}
                  </EuiFlexGroup>
                </div>
              )}

              {messages.map(m => (
                <div
                  key={m.id}
                  style={{
                    marginBottom: 8,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: m.role === 'user' ? 'flex-end' : 'flex-start',
                  }}
                >
                  <EuiText size="xs" color="subdued" style={{ marginBottom: 2, paddingLeft: 2, paddingRight: 2 }}>
                    {m.role === 'user' ? userId : 'Lumio Support'}
                  </EuiText>

                  <EuiPanel
                    paddingSize="s"
                    color={m.role === 'user' ? 'primary' : 'subdued'}
                    hasBorder={m.role === 'assistant'}
                    style={{
                      maxWidth: '85%',
                      width: m.role === 'user' ? 'auto' : '100%',
                    }}
                  >
                    {m.role === 'assistant' ? (
                      <MarkdownContent
                        content={m.content || (!m.isComplete ? '…' : '')}
                      />
                    ) : (
                      <EuiText size="s">{m.content}</EuiText>
                    )}

                    {m.toolCalls.length > 0 && (
                      <div style={{ marginTop: 6 }}>
                        {m.toolCalls.map(tc => (
                          <div key={tc.id} style={{ marginBottom: 2 }}>
                            <EuiHealth color={tc.result ? 'success' : 'warning'}>
                              <EuiText size="xs" color="subdued">
                                <code style={{ fontSize: 11 }}>
                                  {tc.name}({JSON.stringify(tc.arguments)})
                                  {tc.name === 'recall_memory' && tc.result &&
                                    typeof tc.result === 'object' &&
                                    'count' in (tc.result as Record<string, unknown>)
                                    ? ` → ${(tc.result as { count: number }).count} hits`
                                    : ''}
                                </code>
                              </EuiText>
                            </EuiHealth>
                          </div>
                        ))}
                      </div>
                    )}
                  </EuiPanel>
                </div>
              ))}

              {error && (
                <EuiText size="s" color="danger" style={{ marginTop: 8 }}>
                  Error: {error}
                </EuiText>
              )}
            </div>

            {/* ── Input bar — fixed at bottom of chat panel ── */}
            <div style={{ flexShrink: 0, paddingTop: 8, borderTop: '1px solid var(--euiColorLightShade)' }}>
              <EuiFlexGroup gutterSize="s" alignItems="center" responsive={false}>
                <EuiFlexItem>
                  <EuiFieldText
                    fullWidth
                    placeholder={`Message Lumio Support as ${userId}…`}
                    value={draft}
                    onChange={e => setDraft(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        handleSend()
                      }
                    }}
                    disabled={isStreaming}
                  />
                </EuiFlexItem>
                <EuiFlexItem grow={false}>
                  <EuiButton
                    fill
                    onClick={handleSend}
                    isLoading={isStreaming}
                    isDisabled={!draft.trim()}
                    minWidth={80}
                  >
                    Send
                  </EuiButton>
                </EuiFlexItem>
                <EuiFlexItem grow={false}>
                  <EuiButtonEmpty size="s" onClick={reset} isDisabled={isStreaming}>
                    Clear
                  </EuiButtonEmpty>
                </EuiFlexItem>
              </EuiFlexGroup>
            </div>

          </EuiPanel>
        </div>

        {/* ── Memory Inspector ─────────────────────────────── */}
        <div style={{ flex: 1, minWidth: 340, maxWidth: 420, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <MemoryInspector
            userId={userId}
            highlightRecalled={recalledIds}
            highlightWritten={writtenIds}
            refreshKey={refreshKey}
            isConsolidating={isConsolidating}
          />
        </div>

      </div>
    </div>
  )
}
