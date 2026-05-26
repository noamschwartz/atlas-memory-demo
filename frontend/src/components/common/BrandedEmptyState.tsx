/**
 * BrandedEmptyState — Reusable empty state component with brand theming.
 *
 * Use this instead of bare "no data" text. Every empty list, grid, accordion,
 * or search result set should show a visual element and actionable text.
 *
 * Props:
 *   - iconType: EUI icon name (e.g., "search", "package", "heart")
 *   - imageUrl: Optional image URL (takes priority over iconType)
 *   - title: Primary message
 *   - body: Secondary descriptive text
 *   - actions: Optional CTA buttons (ReactNode)
 *   - size: "s" | "m" | "l" — controls spacing and icon/image size
 *
 * Works with zero brand CSS variables set — falls back to EUI defaults.
 */

import {
  EuiEmptyPrompt,
  EuiIcon,
  EuiText,
  EuiTitle,
  EuiSpacer,
} from '@elastic/eui'
import type { ReactNode } from 'react'
import { PhotoStrip, type PhotoStripImage } from './PhotoStrip'

interface BrandedEmptyStateProps {
  /** EUI icon name for the empty state visual */
  iconType?: string
  /** Image URL — overrides iconType when provided */
  imageUrl?: string
  /** Photo strip images — renders a row of photos above the text for visual richness */
  photoStrip?: PhotoStripImage[]
  /** Photo strip shape (default: 'rounded') */
  photoStripShape?: 'circle' | 'rounded' | 'square'
  /** Primary heading text */
  title: string
  /** Secondary body text */
  body?: string
  /** CTA buttons or links */
  actions?: ReactNode
  /** Size variant */
  size?: 's' | 'm' | 'l'
}

const ICON_SIZES: Record<string, 'xl' | 'xxl'> = {
  s: 'xl',
  m: 'xxl',
  l: 'xxl',
}

const IMAGE_SIZES: Record<string, number> = {
  s: 80,
  m: 120,
  l: 180,
}

export function BrandedEmptyState({
  iconType = 'package',
  imageUrl,
  photoStrip,
  photoStripShape,
  title,
  body,
  actions,
  size = 'm',
}: BrandedEmptyStateProps) {
  const stripSize = size === 's' ? 60 : size === 'l' ? 100 : 80

  const icon = photoStrip && photoStrip.length > 0 ? (
    <>
      <PhotoStrip images={photoStrip} shape={photoStripShape} size={stripSize} />
      <EuiSpacer size="m" />
    </>
  ) : imageUrl ? (
    <img
      src={imageUrl}
      alt=""
      loading="lazy"
      style={{
        width: IMAGE_SIZES[size],
        height: IMAGE_SIZES[size],
        objectFit: 'contain',
        borderRadius: 'var(--brand-border-radius, 6px)',
        opacity: 0.85,
      }}
    />
  ) : (
    <EuiIcon
      type={iconType}
      size={ICON_SIZES[size]}
      color="var(--brand-primary, var(--euiColorPrimary))"
    />
  )

  return (
    <EuiEmptyPrompt
      icon={icon}
      title={
        <EuiTitle size={size === 'l' ? 'm' : 's'}>
          <h2 style={{ color: 'var(--brand-text-primary, var(--euiTitleColor))' }}>
            {title}
          </h2>
        </EuiTitle>
      }
      body={
        body ? (
          <EuiText
            size={size === 's' ? 's' : 'm'}
            color="subdued"
          >
            <p>{body}</p>
          </EuiText>
        ) : undefined
      }
      actions={actions}
      style={{
        maxWidth: size === 's' ? 320 : 480,
        margin: '0 auto',
        padding: size === 's' ? '16px 0' : '32px 0',
      }}
    />
  )
}

export default BrandedEmptyState
