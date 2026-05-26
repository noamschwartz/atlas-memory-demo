/**
 * MemoryInspector — compact three-tab live view of episodic / semantic /
 * procedural memory. EuiPanel wrapper uses paddingSize="none" so all spacing
 * is explicit. Header + tabs are flex-shrink:0; list scrolls in remaining flex space.
 */

import { useEffect, useMemo, useState } from 'react'
import {
  EuiBadge,
  EuiEmptyPrompt,
  EuiFlexGroup,
  EuiFlexItem,
  EuiPanel,
  EuiTab,
  EuiTabs,
  EuiText,
  EuiToolTip,
} from '@elastic/eui'
import {
  MemoryItem,
  MemoryType,
  listMemories,
} from './api'

interface Props {
  userId: string
  highlightRecalled: string[]
  highlightWritten: string[]
  refreshKey: number
  isConsolidating?: boolean
}

const TABS: { type: MemoryType; label: string }[] = [
  { type: 'semantic',   label: 'Semantic' },
  { type: 'episodic',   label: 'Episodic' },
  { type: 'procedural', label: 'Procedural' },
]

function pickText(src: Record<string, unknown>, type: MemoryType): string {
  if (type === 'procedural') {
    return (src.name as string) || (src.trigger_text as string) || (src.description as string) || ''
  }
  return (src.text as string) || ''
}

function pickMeta(src: Record<string, unknown>, type: MemoryType): string {
  if (type === 'semantic') {
    const fact = (src.fact_type as string) || 'fact'
    const conf = src.confidence as number | undefined
    return conf != null ? `${fact} · conf ${conf.toFixed(2)}` : fact
  }
  if (type === 'episodic') {
    const ts = src.timestamp as string | undefined
    const role = (src.role as string) || (src.event_type as string) || 'event'
    const when = ts
      ? new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
      : ''
    return when ? `${role} · ${when}` : role
  }
  const steps = (src.steps as unknown[] | undefined)?.length ?? 0
  const ok = (src.success_count as number) ?? 0
  const fail = (src.failure_count as number) ?? 0
  const counts = (ok > 0 || fail > 0) ? `  ✓ ${ok}  ✗ ${fail}` : ''
  return `${steps} steps · v${(src.version as number) ?? 1}${counts}`
}

function MemoryCard({ item, type, recalled, written }: {
  item: MemoryItem; type: MemoryType; recalled: boolean; written: boolean
}) {
  const text = pickText(item.source, type)
  const meta = pickMeta(item.source, type)
  const borderColor = written
    ? 'var(--euiColorSuccess)'
    : recalled ? 'var(--euiColorPrimary)' : 'var(--euiColorLightShade)'

  return (
    <div style={{
      marginBottom: 5,
      padding: '7px 10px',
      borderRadius: 4,
      border: `1px solid ${borderColor}`,
      backgroundColor: written
        ? 'rgba(0,148,78,0.08)'
        : recalled ? 'rgba(0,119,204,0.08)' : 'transparent',
    }}>
      <EuiFlexGroup gutterSize="xs" alignItems="flexStart" responsive={false}>
        <EuiFlexItem>
          <EuiText size="s" style={{ lineHeight: 1.4 }}>
            {text || <em style={{ color: 'var(--euiColorDarkShade)' }}>(empty)</em>}
          </EuiText>
          <EuiText size="xs" color="subdued" style={{ marginTop: 2 }}>{meta}</EuiText>
        </EuiFlexItem>
        {(written || recalled) && (
          <EuiFlexItem grow={false} style={{ paddingTop: 1 }}>
            <EuiToolTip content={written ? 'Written this session' : 'Used by Atlas this turn'}>
              <EuiBadge color={written ? 'success' : 'hollow'} style={{ fontSize: 10, padding: '1px 5px' }}>
                {written ? 'new' : 'recalled'}
              </EuiBadge>
            </EuiToolTip>
          </EuiFlexItem>
        )}
      </EuiFlexGroup>
    </div>
  )
}

export function MemoryInspector({ userId, highlightRecalled, highlightWritten, refreshKey, isConsolidating }: Props) {
  const [tab, setTab] = useState<MemoryType>('semantic')
  const [items, setItems] = useState<MemoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const recalledSet = useMemo(() => new Set(highlightRecalled), [highlightRecalled])
  const writtenSet  = useMemo(() => new Set(highlightWritten),  [highlightWritten])

  useEffect(() => {
    let cancelled = false
    setLoading(true); setErr(null)
    listMemories(userId, tab, 100)
      .then(rows => { if (!cancelled) setItems(rows) })
      .catch(e   => { if (!cancelled) setErr((e as Error).message) })
      .finally(()=> { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [userId, tab, refreshKey])

  return (
    <EuiPanel hasBorder paddingSize="none"
      style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>

      {/* ── Header ─────────────────────────────────────────── */}
      <div style={{ flexShrink: 0, padding: '10px 12px 0', borderBottom: '1px solid var(--euiColorLightShade)' }}>
        <EuiFlexGroup alignItems="center" justifyContent="spaceBetween" gutterSize="s" responsive={false}>
          <EuiFlexItem grow={false}>
            <EuiText size="s">
              <strong>Memory Inspector</strong>
              <span style={{ color: 'var(--euiColorDarkShade)', fontWeight: 400 }}> — {userId}</span>
            </EuiText>
          </EuiFlexItem>
          {isConsolidating && (
            <EuiFlexItem grow={false}>
              <EuiText size="xs" color="subdued" style={{ fontStyle: 'italic' }}>
                ⚙ consolidating…
              </EuiText>
            </EuiFlexItem>
          )}
        </EuiFlexGroup>

        {/* Tabs sit inside the header block so the border runs through them */}
        <EuiTabs size="s">
          {TABS.map(t => (
            <EuiTab key={t.type} isSelected={tab === t.type} onClick={() => setTab(t.type)}>
              {t.label}
            </EuiTab>
          ))}
        </EuiTabs>
      </div>

      {/* ── Scrollable list ──────────────────────────────── */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, padding: '8px 12px 12px' }}>
        {loading && <EuiText size="xs" color="subdued" style={{ padding: '8px 0' }}>Loading…</EuiText>}
        {err     && <EuiText size="xs" color="danger"  style={{ padding: '8px 0' }}>{err}</EuiText>}
        {!loading && !err && items.length === 0 && (
          <EuiEmptyPrompt
            iconType="memory" titleSize="xs"
            title={<h4>No {tab} memory yet</h4>}
            body={<p style={{ fontSize: 12 }}>Memory will appear here as Atlas writes during the chat.</p>}
            paddingSize="s"
          />
        )}
        {items.map(it => (
          <MemoryCard key={it.id} item={it} type={tab}
            recalled={recalledSet.has(it.id)} written={writtenSet.has(it.id)} />
        ))}
      </div>
    </EuiPanel>
  )
}
