/**
 * HeroSection — Reusable hero banner with image, overlay, and content.
 *
 * Handles the common pattern of: background image + semi-transparent overlay
 * + centered content (title, subtitle, CTAs). Falls back gracefully to brand
 * gradients when no image is provided.
 *
 * Usage:
 *   <HeroSection imageUrl="/brands/acme/images/hero.jpg" overlayColor="rgba(0,0,0,0.55)">
 *     <h1>Welcome</h1>
 *   </HeroSection>
 *
 *   // Compact mode for page section headers
 *   <HeroSection compact>
 *     <EuiTitle><h1>Search Results</h1></EuiTitle>
 *     <SearchBar />
 *   </HeroSection>
 *
 *   // Auto-reads brand heroImage when no imageUrl is passed
 *   <HeroSection title="Welcome" subtitle="Discover products" />
 */

import type { CSSProperties, ReactNode } from 'react'
import { EuiSpacer } from '@elastic/eui'
import { useBrand } from '../providers/BrandedThemeProvider'

export interface HeroSectionProps {
  /** Shorthand title — rendered as a responsive h1. Use children for custom layout. */
  title?: ReactNode
  /** Shorthand subtitle — rendered below title. Use children for custom layout. */
  subtitle?: ReactNode
  /** Action buttons rendered below subtitle */
  actions?: ReactNode
  /** Full custom content — overrides title/subtitle/actions when provided */
  children?: ReactNode
  /** Background image URL. Falls back to brand heroImage, then brand gradient. */
  imageUrl?: string
  /** CSS background-position for the image (default: brand setting or 'center') */
  imagePosition?: string
  /** Overlay color. Default: brand overlay or semi-transparent brand primary. */
  overlayColor?: string
  /** Overlay opacity 0-1 (default: 1 — use overlayColor's alpha for transparency) */
  overlayOpacity?: number
  /** Minimum height in px (default: 300, compact: 80) */
  minHeight?: number
  /** Compact mode for page-level section headers (smaller padding, no centering) */
  compact?: boolean
  /** Max content width in px (default: 640, compact: 1400) */
  maxWidth?: number
  /** Extra styles on the outer wrapper */
  style?: CSSProperties
  /** Extra styles on the content container */
  contentStyle?: CSSProperties
}

export function HeroSection({
  title,
  subtitle,
  actions,
  children,
  imageUrl,
  imagePosition,
  overlayColor,
  overlayOpacity = 1,
  minHeight,
  compact = false,
  maxWidth,
  style,
  contentStyle,
}: HeroSectionProps) {
  const { brand } = useBrand()

  const resolvedImageUrl = imageUrl ?? brand.heroImage?.url
  const resolvedPosition = imagePosition ?? brand.heroImage?.position ?? 'center'
  const resolvedOverlay =
    overlayColor ??
    brand.heroImage?.overlay ??
    'var(--brand-primary, rgba(0, 0, 0, 0.5))'
  const resolvedMinHeight = minHeight ?? (compact ? undefined : 300)
  const resolvedMaxWidth = maxWidth ?? (compact ? 1400 : 640)

  const hasImage = !!resolvedImageUrl

  const wrapperStyle: CSSProperties = {
    position: 'relative',
    overflow: 'hidden',
    width: '100%',
    minHeight: resolvedMinHeight,
    display: 'flex',
    alignItems: compact ? 'flex-end' : 'center',
    justifyContent: 'center',
    ...(hasImage
      ? {
          backgroundImage: `url(${resolvedImageUrl})`,
          backgroundSize: 'cover',
          backgroundPosition: resolvedPosition,
        }
      : {
          background:
            brand.gradients?.hero ??
            brand.gradients?.primary ??
            'var(--brand-gradient-primary, linear-gradient(135deg, var(--euiColorPrimary) 0%, var(--euiColorAccent) 100%))',
        }),
    ...style,
  }

  const overlayStyle: CSSProperties = {
    position: 'absolute',
    inset: 0,
    backgroundColor: resolvedOverlay,
    opacity: overlayOpacity,
  }

  const innerStyle: CSSProperties = {
    position: 'relative',
    zIndex: 1,
    width: '100%',
    maxWidth: resolvedMaxWidth,
    margin: '0 auto',
    padding: compact ? '16px 24px' : '40px 24px',
    textAlign: compact ? 'left' : 'center',
    ...contentStyle,
  }

  const hasShorthand = title || subtitle || actions
  const useShorthand = hasShorthand && !children

  return (
    <section style={wrapperStyle}>
      {hasImage && <div style={overlayStyle} aria-hidden />}

      <div style={innerStyle}>
        {useShorthand ? (
          <>
            {typeof title === 'string' ? (
              <h1
                style={{
                  fontFamily: 'var(--brand-font-heading, inherit)',
                  fontSize: compact ? '1.5rem' : 'clamp(2rem, 5vw, 3rem)',
                  color: '#FFFFFF',
                  margin: 0,
                  textShadow: '0 1px 4px rgba(0,0,0,0.3)',
                }}
              >
                {title}
              </h1>
            ) : (
              title
            )}
            {subtitle && (
              <p
                style={{
                  fontSize: compact ? '0.9rem' : '1.125rem',
                  color: 'rgba(255,255,255,0.95)',
                  marginTop: compact ? 4 : 12,
                  lineHeight: 1.5,
                }}
              >
                {subtitle}
              </p>
            )}
            {actions && (
              <>
                <EuiSpacer size={compact ? 's' : 'm'} />
                {actions}
              </>
            )}
          </>
        ) : (
          children
        )}
      </div>
    </section>
  )
}

export default HeroSection
