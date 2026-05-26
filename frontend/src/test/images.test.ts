import { describe, it, expect } from 'vitest'
import { getStockCategory, unsplash, STOCK_IMAGES } from '../utils/images'

describe('getStockCategory', () => {
  it.each([
    ['media intelligence platform', 'news'],
    ['hospital patient records', 'healthcare'],
    ['investment banking portal', 'finance'],
    ['government policy database', 'government'],
    ['manufacturing equipment catalog', 'industrial'],
    ['university course search', 'education'],
    ['grocery delivery service', 'food'],
    ['fashion clothing store', 'fashion'],
    ['real estate listings', 'home'],
    ['cybersecurity software', 'tech'],
    ['ecommerce product catalog', 'retail'],
    ['enterprise consulting', 'office'],
    ['climate sustainability tracker', 'nature'],
    ['travel wellness guide', 'lifestyle'],
  ])('maps "%s" to "%s"', (domain, expected) => {
    expect(getStockCategory(domain)).toBe(expected)
  })

  it('is case-insensitive', () => {
    expect(getStockCategory('HOSPITAL Records')).toBe('healthcare')
    expect(getStockCategory('News Broadcasting')).toBe('news')
  })

  it('defaults to "tech" for unrecognised domains', () => {
    expect(getStockCategory('random unknown domain')).toBe('tech')
    expect(getStockCategory('')).toBe('tech')
  })

  it('returns a key that exists in STOCK_IMAGES', () => {
    const domains = [
      'news site', 'hospital', 'banking', 'government',
      'manufacturing', 'university', 'grocery', 'fashion',
      'furniture', 'software', 'retail', 'consulting',
      'environment', 'travel', 'something unknown',
    ]
    for (const domain of domains) {
      const category = getStockCategory(domain)
      expect(STOCK_IMAGES[category]).toBeDefined()
      expect(STOCK_IMAGES[category].length).toBeGreaterThan(0)
    }
  })
})

describe('unsplash', () => {
  it('builds a URL with width and height', () => {
    const url = unsplash('abc-123', 800, 400)
    expect(url).toBe('https://images.unsplash.com/photo-abc-123?w=800&h=400&fit=crop')
  })

  it('builds a URL with width only', () => {
    const url = unsplash('abc-123', 800)
    expect(url).toBe('https://images.unsplash.com/photo-abc-123?w=800&fit=crop')
  })

  it('includes extra options', () => {
    const url = unsplash('abc-123', 800, 400, { q: 80 })
    expect(url).toContain('q=80')
    expect(url).toContain('w=800')
    expect(url).toContain('h=400')
  })
})

describe('STOCK_IMAGES', () => {
  it('has at least 14 categories', () => {
    expect(Object.keys(STOCK_IMAGES).length).toBeGreaterThanOrEqual(14)
  })

  it('every category has at least 4 images with valid ids', () => {
    for (const [category, images] of Object.entries(STOCK_IMAGES)) {
      expect(images.length, `${category} should have >= 4 images`).toBeGreaterThanOrEqual(4)
      for (const img of images) {
        expect(img.id, `${category} image missing id`).toBeTruthy()
        expect(img.credit, `${category} image missing credit`).toBeTruthy()
      }
    }
  })
})
