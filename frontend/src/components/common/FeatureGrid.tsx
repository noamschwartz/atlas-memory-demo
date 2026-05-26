/**
 * FeatureGrid — Responsive card grid for features, categories, or solutions.
 *
 * Renders a 3-column (desktop), 2-column (tablet), 1-column (mobile) grid
 * of cards with optional images, titles, descriptions, and click actions.
 * Uses EUI's gutterSize="l" (16px) for consistent spacing.
 * Handles image loading errors gracefully with brand-colored fallbacks.
 *
 * Usage:
 *   import { FeatureGrid } from '../components/common/FeatureGrid'
 *   import { unsplash, STOCK_IMAGES } from '../utils/images'
 *
 *   <FeatureGrid
 *     items={[
 *       { title: 'Search', description: 'Find anything', imageUrl: unsplash(STOCK_IMAGES.tech[0].id, 400, 200) },
 *       { title: 'Analyze', description: 'AI insights', icon: 'visMapRegion' },
 *     ]}
 *     onItemClick={(item) => navigate(item.path)}
 *   />
 *
 *   // Compact variant for smaller sections
 *   <FeatureGrid items={items} columns={4} imageHeight={120} compact />
 */

import { useState, useCallback, type CSSProperties } from 'react'
import {
  EuiFlexGroup,
  EuiFlexItem,
  EuiCard,
  EuiIcon,
} from '@elastic/eui'

/** Valid EUI BetaBadge color values */
type BadgeColor = 'accent' | 'subdued' | 'hollow' | 'warning'

export interface FeatureGridItem {
  /** Unique key for the item */
  id: string
  /** Card title */
  title: string
  /** Card description text */
  description: string
  /** Image URL for the card header */
  imageUrl?: string
  /** EUI icon name — used as fallback when no imageUrl, or as card icon */
  icon?: string
  /** Navigation path or action identifier */
  path?: string
  /** Badge text shown on the card */
  badge?: string
  /** Badge color — must be a valid EUI BetaBadge color */
  badgeColor?: BadgeColor
}

export interface FeatureGridProps {
  items: FeatureGridItem[]
  /** Number of columns at desktop width (default: 3) */
  columns?: 2 | 3 | 4
  /** Called when a card is clicked, receives the item */
  onItemClick?: (item: FeatureGridItem) => void
  /** Image height in px (default: 180) */
  imageHeight?: number
  /** Compact mode — smaller padding and text */
  compact?: boolean
}

const MIN_WIDTHS: Record<number, number> = {
  2: 320,
  3: 280,
  4: 220,
}

export function FeatureGrid({
  items,
  columns = 3,
  onItemClick,
  imageHeight = 180,
  compact = false,
}: FeatureGridProps) {
  const [failedImages, setFailedImages] = useState<Set<string>>(new Set())

  const handleImageError = useCallback((id: string) => {
    setFailedImages(prev => new Set(prev).add(id))
  }, [])

  if (items.length === 0) return null

  const minWidth = MIN_WIDTHS[columns] ?? 280

  return (
    <EuiFlexGroup gutterSize="l" wrap responsive>
      {items.map(item => {
        const showImage = item.imageUrl && !failedImages.has(item.id)
        const cardImage = showImage ? (
          <img
            src={item.imageUrl}
            alt=""
            loading="lazy"
            onError={() => handleImageError(item.id)}
            style={{
              width: '100%',
              height: imageHeight,
              objectFit: 'cover',
            }}
          />
        ) : undefined

        const cardIcon = !showImage && item.icon ? (
          <EuiIcon
            type={item.icon}
            size="xxl"
            color="var(--brand-primary, var(--euiColorPrimary))"
          />
        ) : undefined

        const cardStyle: CSSProperties = {
          minWidth,
          flex: `1 1 ${minWidth}px`,
          maxWidth: columns === 2 ? 520 : 400,
        }

        return (
          <EuiFlexItem key={item.id} grow={false} style={cardStyle}>
            <EuiCard
              title={item.title}
              description={item.description}
              image={cardImage}
              icon={cardIcon}
              paddingSize={compact ? 's' : 'm'}
              onClick={onItemClick ? () => onItemClick(item) : undefined}
              hasBorder
              betaBadgeProps={
                item.badge
                  ? { label: item.badge, color: item.badgeColor ?? 'accent' }
                  : undefined
              }
            />
          </EuiFlexItem>
        )
      })}
    </EuiFlexGroup>
  )
}

export default FeatureGrid
