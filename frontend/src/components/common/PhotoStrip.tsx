/**
 * PhotoStrip — A horizontal row of images for visual richness.
 *
 * Use in empty states, section intros, or anywhere you want a row of
 * curated imagery to break up text-heavy layouts.
 *
 * Usage:
 *   import { PhotoStrip } from '../components/common/PhotoStrip'
 *   import { unsplash, STOCK_IMAGES } from '../utils/images'
 *
 *   <PhotoStrip
 *     images={STOCK_IMAGES.food.slice(0, 3).map(img => ({
 *       url: unsplash(img.id, 120, 120),
 *     }))}
 *   />
 *
 *   // Circular avatars
 *   <PhotoStrip images={[...]} shape="circle" size={64} />
 */

import { EuiFlexGroup, EuiFlexItem } from '@elastic/eui'

export interface PhotoStripImage {
  url: string
  alt?: string
}

export interface PhotoStripProps {
  images: PhotoStripImage[]
  /** Shape of each image: 'circle' | 'rounded' | 'square' (default: 'rounded') */
  shape?: 'circle' | 'rounded' | 'square'
  /** Size of each image in px (default: 80) */
  size?: number
  /** Gap between images in px (default: 12) */
  gap?: number
}

const BORDER_RADIUS: Record<string, string> = {
  circle: '50%',
  rounded: '8px',
  square: '0',
}

export function PhotoStrip({
  images,
  shape = 'rounded',
  size = 80,
  gap = 12,
}: PhotoStripProps) {
  if (images.length === 0) return null

  return (
    <EuiFlexGroup
      gutterSize="none"
      justifyContent="center"
      alignItems="center"
      responsive={false}
      wrap={false}
      style={{ gap }}
    >
      {images.map((img, i) => (
        <EuiFlexItem key={i} grow={false}>
          <img
            src={img.url}
            alt={img.alt ?? ''}
            loading="lazy"
            style={{
              width: size,
              height: size,
              objectFit: 'cover',
              borderRadius: BORDER_RADIUS[shape],
              boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
              flexShrink: 0,
            }}
          />
        </EuiFlexItem>
      ))}
    </EuiFlexGroup>
  )
}

export default PhotoStrip
