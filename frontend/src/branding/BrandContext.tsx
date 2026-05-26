import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'
import { 
  BrandTheme, 
  brands, 
  getSelectedBrandId, 
  setSelectedBrand as persistBrand,
  generateBrandCssVariables,
  addBrand,
} from './index'

// ============================================================================
// Brand Context
// ============================================================================

interface BrandContextType {
  brand: BrandTheme
  brandId: string
  setBrand: (brandId: string) => void
  availableBrands: BrandTheme[]
  refreshBrands: () => Promise<void>
}

const BrandContext = createContext<BrandContextType | null>(null)

// ============================================================================
// API Brand to Theme Converter
// ============================================================================

interface ApiBrand {
  id: string
  name: string
  colors: {
    primary: string
    accent: string
    background: string
    text: string
  }
  logoLight?: { url: string; alt: string }
  logoDark?: { url: string; alt: string }
  colorsDark?: Partial<BrandTheme['colors']>
}

function apiBrandToTheme(api: ApiBrand): BrandTheme {
  return {
    id: api.id,
    name: api.name,
    sourceUrl: '',
    extractedAt: '',
    colors: {
      primary: api.colors.primary,
      accent: api.colors.accent,
      background: api.colors.background,
      white: '#FFFFFF',
      black: '#1A1C21',
      textPrimary: api.colors.text,
      textBody: api.colors.text,
      border: '#D3DAE6',
    },
    colorsDark: api.colorsDark,
    fonts: {
      heading: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
      body: '"Inter", -apple-system, BlinkMacSystemFont, sans-serif',
      fallback: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    },
    spacing: {
      borderRadius: '6px',
      borderRadiusSmall: '4px',
    },
    logo: {
      svgDataUrl: api.logoLight?.url || '',
      alt: api.logoLight?.alt || api.name,
    },
  }
}

// ============================================================================
// Brand Provider
// ============================================================================

interface BrandProviderProps {
  children: ReactNode
  defaultBrandId?: string
}

export function BrandProvider({ children, defaultBrandId }: BrandProviderProps) {
  const [brandId, setBrandId] = useState<string>(() => {
    return defaultBrandId || getSelectedBrandId()
  })
  const [allBrands, setAllBrands] = useState<Record<string, BrandTheme>>(brands)

  const brand = allBrands[brandId] || allBrands.default || brands.default

  // Load brands from API on mount
  const refreshBrands = useCallback(async () => {
    try {
      const response = await fetch('/api/branding/')
      if (response.ok) {
        const apiBrands: ApiBrand[] = await response.json()
        
        // Merge API brands with in-memory brands (vibe-coded themes take priority)
        const merged = { ...brands }
        for (const apiBrand of apiBrands) {
          if (!merged[apiBrand.id]) {
            const theme = apiBrandToTheme(apiBrand)
            merged[apiBrand.id] = theme
            addBrand(theme) // Also add to in-memory registry
          }
        }
        setAllBrands(merged)
      }
    } catch {
      // API not available, use in-memory brands only
      console.log('Brand API not available, using in-memory brands')
    }
  }, [])

  useEffect(() => {
    refreshBrands()
  }, [refreshBrands])

  // Inject CSS variables when brand changes
  useEffect(() => {
    const styleId = 'brand-css-variables'
    let styleEl = document.getElementById(styleId) as HTMLStyleElement | null
    
    if (!styleEl) {
      styleEl = document.createElement('style')
      styleEl.id = styleId
      document.head.appendChild(styleEl)
    }
    
    styleEl.textContent = generateBrandCssVariables(brand)
    
    // Also set a data attribute on body for CSS targeting
    document.body.setAttribute('data-brand', brandId)
    
    return () => {
      // Cleanup on unmount
    }
  }, [brand, brandId])

  const setBrand = (newBrandId: string) => {
    if (allBrands[newBrandId]) {
      setBrandId(newBrandId)
      persistBrand(newBrandId)
    }
  }

  const availableBrands = Object.values(allBrands)

  return (
    <BrandContext.Provider value={{ brand, brandId, setBrand, availableBrands, refreshBrands }}>
      {children}
    </BrandContext.Provider>
  )
}

// ============================================================================
// Hook to access brand context
// ============================================================================

export function useBrand(): BrandContextType {
  const context = useContext(BrandContext)
  if (!context) {
    throw new Error('useBrand must be used within a BrandProvider')
  }
  return context
}

// ============================================================================
// HOC to wrap components with brand styles
// ============================================================================

export function withBrand<P extends object>(
  Component: React.ComponentType<P & { brand: BrandTheme }>
) {
  return function WithBrandComponent(props: P) {
    const { brand } = useBrand()
    // @ts-expect-error - Type inference issue with HOC, but works at runtime
    return <Component {...props} brand={brand} />
  }
}

