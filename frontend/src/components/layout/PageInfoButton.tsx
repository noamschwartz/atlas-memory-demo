/**
 * PageInfoButton Component
 * 
 * A subtle, standardized info button that provides contextual help for pages.
 * Appears in the top-right of pages to explain what the page does.
 * 
 * Usage:
 * ```tsx
 * <PageInfoButton
 *   title="MCP Explorer"
 *   description="Test and explore MCP server tools connected to your Agent Builder."
 *   features={[
 *     "View available tools and their parameters",
 *     "Test tools with custom arguments",
 *     "Copy configuration for Cursor/Claude Desktop"
 *   ]}
 *   learnMoreUrl="/docs/mcp"
 * />
 * ```
 */

import { useState } from 'react'
import {
  EuiButtonIcon,
  EuiPopover,
  EuiPopoverTitle,
  EuiText,
  EuiSpacer,
  EuiFlexGroup,
  EuiFlexItem,
  EuiIcon,
  EuiHorizontalRule,
  EuiLink,
  EuiToolTip,
} from '@elastic/eui'

export interface PageInfoButtonProps {
  /** Page title shown in popover header */
  title: string
  /** Brief description of what the page does */
  description: string
  /** List of key features or capabilities */
  features?: string[]
  /** Optional link to more documentation */
  learnMoreUrl?: string
  /** Optional link text (default: "Learn more") */
  learnMoreText?: string
  /** Position of the popover */
  position?: 'downRight' | 'downLeft' | 'downCenter'
  /** Icon color - default is 'text' for subtle appearance */
  iconColor?: 'text' | 'primary' | 'accent'
}

export function PageInfoButton({
  title,
  description,
  features,
  learnMoreUrl,
  learnMoreText = 'Learn more',
  position = 'downLeft',
  iconColor = 'text',
}: PageInfoButtonProps) {
  const [isOpen, setIsOpen] = useState(false)

  const button = (
    <EuiToolTip content={`About ${title}`} position="left">
      <EuiButtonIcon
        iconType="help"
        aria-label={`About ${title}`}
        onClick={() => setIsOpen(!isOpen)}
        color={iconColor}
        display="empty"
        size="s"
        className="page-info-button"
      />
    </EuiToolTip>
  )

  return (
    <>
      <EuiPopover
        button={button}
        isOpen={isOpen}
        closePopover={() => setIsOpen(false)}
        anchorPosition={position}
        panelPaddingSize="m"
        panelStyle={{ maxWidth: '320px' }}
      >
        <EuiPopoverTitle paddingSize="s">
          <EuiFlexGroup gutterSize="s" alignItems="center" responsive={false}>
            <EuiFlexItem grow={false}>
              <EuiIcon type="help" color="primary" />
            </EuiFlexItem>
            <EuiFlexItem>
              <strong>{title}</strong>
            </EuiFlexItem>
          </EuiFlexGroup>
        </EuiPopoverTitle>

        <EuiText size="s">
          <p style={{ margin: 0 }}>{description}</p>
        </EuiText>

        {features && features.length > 0 && (
          <>
            <EuiSpacer size="m" />
            <EuiHorizontalRule margin="none" />
            <EuiSpacer size="s" />
            <EuiText size="xs" color="subdued">
              <strong>Features:</strong>
            </EuiText>
            <EuiSpacer size="xs" />
            <ul style={{ margin: 0, paddingLeft: '16px' }}>
              {features.map((feature, idx) => (
                <li key={idx}>
                  <EuiText size="s">
                    <span>{feature}</span>
                  </EuiText>
                </li>
              ))}
            </ul>
          </>
        )}

        {learnMoreUrl && (
          <>
            <EuiSpacer size="m" />
            <EuiLink href={learnMoreUrl} target="_blank" external>
              {learnMoreText}
            </EuiLink>
          </>
        )}
      </EuiPopover>

      <style>{`
        .page-info-button {
          opacity: 0.5;
          transition: opacity 0.15s ease;
        }
        .page-info-button:hover {
          opacity: 1;
        }
      `}</style>
    </>
  )
}

/**
 * Pre-configured info content for standard pages
 * Use these with PageInfoButton for consistency
 */
export const PAGE_INFO = {
  chat: {
    title: 'AI Chat',
    description: 'Chat with your Elastic Agent Builder AI assistant. Responses stream in real-time with reasoning steps and tool calls visible.',
    features: [
      'Real-time streaming responses',
      'See AI reasoning and tool calls',
      'Conversation history preserved',
    ],
  },
  
  brands: {
    title: 'Brand Editor',
    description: 'Create and manage brand themes for your demos. Set colors, upload logos, and preview how your brand will appear.',
    features: [
      'Create custom brand themes',
      'Set primary and accent colors',
      'Upload light/dark logo variants',
      'Live preview changes',
    ],
  },
  
  branded: {
    title: 'Branded Demo',
    description: 'Preview how your AI assistant looks with the current brand theme applied. Use this to demonstrate to stakeholders.',
    features: [
      'Live brand preview',
      'See all brand colors in action',
      'Test with different themes via ?brand=',
    ],
  },
  
  mcp: {
    title: 'MCP Explorer',
    description: 'Explore and test the Model Context Protocol (MCP) tools available from your Agent Builder. Useful for debugging and development.',
    features: [
      'View all available MCP tools',
      'Test tools with custom arguments',
      'See tool input schemas',
      'Copy IDE configuration',
    ],
    learnMoreUrl: 'https://docs.elastic.co/agent-builder',
  },
  
  audit: {
    title: 'Conversation Audit',
    description: 'View and analyze past conversations with your AI agents. Useful for reviewing interactions and debugging.',
    features: [
      'Browse conversation history',
      'Filter by agent',
      'View full message details',
      'See tool calls and responses',
    ],
  },
  
  a2a: {
    title: 'A2A Coordinator',
    description: 'Multi-agent orchestration using Agent-to-Agent (A2A) protocol. A coordinator LLM routes requests to specialized agents.',
    features: [
      'Coordinate multiple agents',
      'See agent selection in real-time',
      'View inter-agent communication',
    ],
  },
}

