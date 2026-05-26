/**
 * SplitChatContentLayout — Fixed-viewport two-column layout for chat + content.
 *
 * Provides the structural pattern used in agent+tools pages:
 *   - Fixed position below the app header, fills remaining viewport
 *   - No page-level scrolling — both panels scroll internally
 *   - Optional top bar (task switcher, breadcrumbs, etc.)
 *   - Chat panel (left): flex column, fills height
 *   - Content panel (right): bordered card with tab bar + scrollable body
 *
 * Usage:
 *   <SplitChatContentLayout
 *     topBar={<TaskSwitcher tasks={tasks} ... />}
 *     chatPanel={<ChatContainer ... />}
 *     chatTopSlot={<PreferencesForm />}      // optional above chat
 *     tabs={[
 *       { id: 'overview', label: 'Context', icon: 'user' },
 *       { id: 'plan', label: 'Plan', icon: 'calendar', count: 5 },
 *     ]}
 *     activeTabId={activeTab}
 *     onTabChange={setActiveTab}
 *     contentPanel={<>{activeTab === 'overview' && <Overview />}</>}
 *   />
 */

import type { CSSProperties, ReactNode } from 'react'
import { TabBar, type TabDef } from './TabBar'

export interface SplitChatContentLayoutProps {
  /** Optional top bar rendered above the two columns (e.g., TaskSwitcher) */
  topBar?: ReactNode
  /** Content rendered above the chat panel (e.g., preferences form) */
  chatTopSlot?: ReactNode
  /** The chat panel (e.g., ChatContainer). Fills remaining left-column height. */
  chatPanel: ReactNode
  /** Tab definitions for the content panel header */
  tabs: TabDef[]
  /** Currently active tab ID */
  activeTabId: string
  /** Called when a tab is clicked */
  onTabChange: (tabId: string) => void
  /** Content rendered inside the active tab area (scrollable) */
  contentPanel: ReactNode
  /** Header height in px — must match AppHeader (default: 56) */
  headerHeight?: number
  /** Max content width in px (default: 1400) */
  maxWidth?: number
  /** Flex ratio for the chat column (default: 5) */
  chatFlex?: number
  /** Flex ratio for the content column (default: 4) */
  contentFlex?: number
  /** Gap between columns in px (default: 16) */
  gap?: number
  /** Extra styles on the outer fixed container */
  style?: CSSProperties
  /** Content panel padding in px (default: 16) */
  contentPadding?: number
}

export function SplitChatContentLayout({
  topBar,
  chatTopSlot,
  chatPanel,
  tabs,
  activeTabId,
  onTabChange,
  contentPanel,
  headerHeight = 56,
  maxWidth = 1400,
  chatFlex = 5,
  contentFlex = 4,
  gap = 16,
  style,
  contentPadding = 16,
}: SplitChatContentLayoutProps) {
  return (
    <div
      style={{
        position: 'fixed',
        top: headerHeight,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        ...style,
      }}
    >
      {topBar && (
        <div style={{ padding: '10px 24px 0', maxWidth, width: '100%', margin: '0 auto' }}>
          {topBar}
        </div>
      )}

      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          gap,
          padding: '10px 24px 16px',
          maxWidth,
          width: '100%',
          margin: '0 auto',
          overflow: 'hidden',
        }}
      >
        {/* Left column: optional top slot + chat */}
        <div style={{ flex: chatFlex, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {chatTopSlot}
          <div style={{ flex: 1, minHeight: 0 }}>
            {chatPanel}
          </div>
        </div>

        {/* Right column: tabbed content panel */}
        <div
          style={{
            flex: contentFlex,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            borderRadius: 16,
            overflow: 'hidden',
            border: '1px solid var(--euiColorLightShade)',
            background: 'var(--euiColorEmptyShade)',
          }}
        >
          <TabBar tabs={tabs} activeTabId={activeTabId} onTabChange={onTabChange} />

          <div style={{ flex: 1, overflow: 'auto', padding: contentPadding }}>
            {contentPanel}
          </div>
        </div>
      </div>
    </div>
  )
}

export default SplitChatContentLayout
