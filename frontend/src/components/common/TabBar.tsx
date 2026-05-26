/**
 * TabBar + TabButton — Custom tab bar for content panels.
 *
 * A horizontal bar of equal-width buttons with icons, optional badge counts,
 * and "has content" dot indicators. Used inside SplitChatContentLayout or
 * anywhere a compact, styled tab bar is needed.
 *
 * Usage:
 *   <TabBar
 *     tabs={[
 *       { id: 'overview', label: 'Context', icon: 'user' },
 *       { id: 'plan', label: 'Plan', icon: 'calendar', count: 5 },
 *       { id: 'list', label: 'List', icon: 'list', hasContent: true },
 *     ]}
 *     activeTabId="overview"
 *     onTabChange={(id) => setActiveTab(id)}
 *   />
 */

import { EuiBadge, EuiIcon } from '@elastic/eui'

export interface TabDef {
  id: string
  label: string
  icon: string
  /** Badge count shown next to the label */
  count?: number
  /** Green dot indicator when tab has content but no count */
  hasContent?: boolean
}

export interface TabBarProps {
  tabs: TabDef[]
  activeTabId: string
  onTabChange: (tabId: string) => void
}

export function TabBar({ tabs, activeTabId, onTabChange }: TabBarProps) {
  return (
    <div
      style={{
        display: 'flex',
        borderBottom: '1px solid var(--euiColorLightShade)',
        background: 'var(--euiColorLightestShade)',
        flexShrink: 0,
      }}
    >
      {tabs.map((tab) => (
        <TabButton
          key={tab.id}
          active={activeTabId === tab.id}
          onClick={() => onTabChange(tab.id)}
          icon={tab.icon}
          label={tab.label}
          count={tab.count}
          hasContent={tab.hasContent}
        />
      ))}
    </div>
  )
}

function TabButton({
  active,
  onClick,
  icon,
  label,
  count,
  hasContent,
}: {
  active: boolean
  onClick: () => void
  icon: string
  label: string
  count?: number
  hasContent?: boolean
}) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        padding: '12px 8px',
        border: 'none',
        borderBottom: active ? '2px solid var(--euiColorPrimary)' : '2px solid transparent',
        background: active ? 'var(--euiColorEmptyShade)' : 'transparent',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        color: active ? 'var(--euiColorPrimary)' : 'var(--euiTextSubduedColor)',
        fontWeight: active ? 600 : 400,
        fontSize: 13,
        transition: 'all 0.15s ease',
      }}
    >
      <EuiIcon type={icon} size="s" />
      {label}
      {count !== undefined && count > 0 && (
        <EuiBadge color={active ? 'primary' : 'hollow'} style={{ fontSize: 10 }}>
          {count}
        </EuiBadge>
      )}
      {hasContent && !count && (
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: 'var(--euiColorSuccess)',
          }}
        />
      )}
    </button>
  )
}

export default TabBar
