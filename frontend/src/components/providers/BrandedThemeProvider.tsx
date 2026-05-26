import { useState, useEffect, useCallback, createContext, useContext, type ReactNode } from 'react'
import { EuiProvider, EuiThemeColorMode } from '@elastic/eui'
import createCache from '@emotion/cache'
import { BrandTheme, brands as staticBrands, getSelectedBrandId, setSelectedBrand as persistBrand, addBrand } from '../../branding'

/**
 * Branded Theme Provider
 * 
 * Combines brand theming with dark/light mode:
 * - Brand colors adapt to dark/light mode
 * - Single provider for entire app
 * - Injects CSS variables globally
 */

// Create Emotion cache for EUI styles
const euiCache = createCache({
  key: 'eui',
  container: document.head,
})
euiCache.compat = true

// ============================================================================
// Combined Context Type
// ============================================================================

interface BrandedThemeContextType {
  // Theme mode
  colorMode: EuiThemeColorMode
  setColorMode: (mode: EuiThemeColorMode) => void
  toggleColorMode: () => void
  
  // Branding
  brand: BrandTheme
  brandId: string
  setBrand: (brandId: string) => void
  availableBrands: BrandTheme[]
  refreshBrands: () => Promise<void>
}

const BrandedThemeContext = createContext<BrandedThemeContextType | null>(null)

// ============================================================================
// Hook to access context
// ============================================================================

export function useBrandedTheme(): BrandedThemeContextType {
  const context = useContext(BrandedThemeContext)
  if (!context) {
    throw new Error('useBrandedTheme must be used within BrandedThemeProvider')
  }
  return context
}

// Legacy hooks for backwards compatibility
export function useTheme() {
  const { colorMode, setColorMode, toggleColorMode } = useBrandedTheme()
  return { colorMode, setColorMode, toggleColorMode }
}

export function useBrand() {
  const { brand, brandId, setBrand, availableBrands, refreshBrands } = useBrandedTheme()
  return { brand, brandId, setBrand, availableBrands, refreshBrands }
}

// ============================================================================
// CSS Variable Generation
// ============================================================================

function generateCssVariables(brand: BrandTheme, colorMode: EuiThemeColorMode): string {
  const isDark = colorMode === 'dark'
  
  // Base colors from brand
  const baseColors = brand.colors
  
  // Dark mode overrides
  const darkColors = brand.colorsDark || {}
  
  // Calculate final colors
  const finalColors = isDark ? {
    // Default dark mode mappings if no override provided
    primary: darkColors.primary || baseColors.primary,
    accent: darkColors.accent || baseColors.accent,
    background: darkColors.background || '#1D1E24',
    surface: darkColors.surface || '#25262E',
    white: darkColors.white || '#25262E',
    black: darkColors.black || '#FFFFFF',
    textPrimary: darkColors.textPrimary || '#FFFFFF',
    textBody: darkColors.textBody || '#B4B7C1',
    border: darkColors.border || '#404040',
    // Merge any other dark overrides
    ...darkColors
  } : {
    // Light mode uses base colors
    ...baseColors
  }
  
  // Generate CSS variables for all keys in finalColors
  const colorVars = Object.entries(finalColors).map(([key, value]) => {
    // Convert camelCase to kebab-case for CSS var name
    const varName = key.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase()
    return `--brand-${varName}: ${value};`
  }).join('\n      ')
  
  // Generate link CSS variables
  const linkVars = brand.links ? `
      /* Link Styling */
      --brand-link-color: ${brand.links.color};
      --brand-link-hover-color: ${brand.links.hoverColor || brand.links.color};
      --brand-link-underline-thickness: ${brand.links.underlineThickness || '1px'};
      --brand-link-underline-offset: ${brand.links.underlineOffset || '.1em'};
      --brand-link-focus-bg: ${brand.links.focus?.backgroundColor || 'transparent'};
      --brand-link-focus-shadow: ${brand.links.focus?.boxShadow || 'none'};` : ''
  
  // Generate focus ring CSS variables
  const focusVars = brand.focusRing ? `
      /* Focus Ring */
      --brand-focus-color: ${brand.focusRing.color};
      --brand-focus-width: ${brand.focusRing.width || '3px'};
      --brand-focus-offset: ${brand.focusRing.offset || '0'};
      --brand-focus-shadow: ${brand.focusRing.boxShadow || `0 0 0 ${brand.focusRing.width || '3px'} ${brand.focusRing.color}`};` : ''
  
  // Generate button CSS variables
  const buttonVars = brand.buttons?.primary ? `
      /* Primary Button */
      --brand-btn-primary-bg: ${brand.buttons.primary.backgroundColor};
      --brand-btn-primary-color: ${brand.buttons.primary.textColor};
      --brand-btn-primary-radius: ${brand.buttons.primary.borderRadius || brand.spacing.borderRadius};
      --brand-btn-primary-shadow: ${brand.buttons.primary.boxShadow || 'none'};
      --brand-btn-primary-border: ${brand.buttons.primary.border || 'none'};
      --brand-btn-primary-padding: ${brand.buttons.primary.padding || '8px 16px'};
      --brand-btn-primary-font-weight: ${brand.buttons.primary.fontWeight || '400'};
      --brand-btn-primary-hover-bg: ${brand.buttons.primary.hover?.backgroundColor || brand.buttons.primary.backgroundColor};
      --brand-btn-primary-focus-shadow: ${brand.buttons.primary.focus?.boxShadow || 'none'};` : ''
  
  const secondaryButtonVars = brand.buttons?.secondary ? `
      /* Secondary Button */
      --brand-btn-secondary-bg: ${brand.buttons.secondary.backgroundColor};
      --brand-btn-secondary-color: ${brand.buttons.secondary.textColor};
      --brand-btn-secondary-radius: ${brand.buttons.secondary.borderRadius || brand.spacing.borderRadius};
      --brand-btn-secondary-shadow: ${brand.buttons.secondary.boxShadow || 'none'};
      --brand-btn-secondary-border: ${brand.buttons.secondary.border || 'none'};
      --brand-btn-secondary-hover-bg: ${brand.buttons.secondary.hover?.backgroundColor || brand.buttons.secondary.backgroundColor};` : ''
  
  // Generate layout CSS variables
  const layoutVars = brand.layout ? `
      /* Layout */
      --brand-max-width: ${brand.layout.maxWidth || '1200px'};
      --brand-container-padding: ${brand.layout.containerPadding || '0 15px'};
      --brand-section-spacing: ${brand.layout.sectionSpacing || '30px'};
      --brand-header-height: ${brand.layout.headerHeight || '48px'};` : `
      /* Layout defaults */
      --brand-header-height: 48px;`

  // Generate gradient CSS variables
  const gradientVars = brand.gradients ? `
      /* Gradients */
      --brand-gradient-primary: ${brand.gradients.primary || 'none'};
      --brand-gradient-accent: ${brand.gradients.accent || 'none'};
      --brand-gradient-hero: ${brand.gradients.hero || 'none'};` : ''

  // Generate hero image CSS variables
  const heroVars = brand.heroImage ? `
      /* Hero Image */
      --brand-hero-image: url('${brand.heroImage.url}');
      --brand-hero-position: ${brand.heroImage.position || 'center'};
      --brand-hero-overlay: ${brand.heroImage.overlay || 'transparent'};` : ''

  // Generate background pattern CSS variable
  const patternVars = brand.backgroundPattern ? `
      /* Background Pattern */
      --brand-background-pattern: ${brand.backgroundPattern};` : ''
  
  // Generate link styles if configured
  const linkStyles = brand.links ? `
    /* Brand Link Styles */
    a:not(.euiLink):not([class*="eui"]) {
      color: var(--brand-link-color);
      text-decoration: underline;
      text-decoration-thickness: var(--brand-link-underline-thickness);
      text-underline-offset: var(--brand-link-underline-offset);
    }
    a:not(.euiLink):not([class*="eui"]):hover {
      color: var(--brand-link-hover-color);
      text-decoration-thickness: max(3px, .1875rem);
    }
    ${brand.links.focus ? `
    a:not(.euiLink):not([class*="eui"]):focus {
      outline: 3px solid transparent;
      background-color: var(--brand-link-focus-bg);
      box-shadow: var(--brand-link-focus-shadow);
      ${brand.links.focus.removeUnderline ? 'text-decoration: none;' : ''}
    }` : ''}` : ''
  
  // Generate focus ring styles if configured
  const focusStyles = brand.focusRing ? `
    /* Brand Focus Ring */
    :focus-visible {
      outline: var(--brand-focus-width) solid var(--brand-focus-color);
      outline-offset: var(--brand-focus-offset);
    }` : ''
  
  // Generate button styles if configured
  const buttonStyles = brand.buttons?.primary ? `
    /* Brand Button Styles */
    .brand-btn-primary,
    button[data-brand-style="primary"] {
      font-family: var(--brand-font-body);
      font-weight: var(--brand-btn-primary-font-weight);
      background-color: var(--brand-btn-primary-bg);
      color: var(--brand-btn-primary-color);
      border-radius: var(--brand-btn-primary-radius);
      box-shadow: var(--brand-btn-primary-shadow);
      border: var(--brand-btn-primary-border);
      padding: var(--brand-btn-primary-padding);
      cursor: pointer;
    }
    .brand-btn-primary:hover,
    button[data-brand-style="primary"]:hover {
      background-color: var(--brand-btn-primary-hover-bg);
    }
    .brand-btn-primary:focus,
    button[data-brand-style="primary"]:focus {
      box-shadow: var(--brand-btn-primary-focus-shadow);
    }` : ''
  
  return `
    :root {
      /* Brand Colors (mode-aware) */
      ${colorVars}
      
      /* Brand Spacing */
      --brand-border-radius: ${brand.spacing.borderRadius};
      --brand-border-radius-small: ${brand.spacing.borderRadiusSmall};
      
      /* Brand Fonts */
      --brand-font-heading: ${brand.fonts.heading};
      --brand-font-body: ${brand.fonts.body};
      
      /* Original brand colors (unmodified) */
      --brand-primary-original: ${brand.colors.primary};
      --brand-accent-original: ${brand.colors.accent};
      ${linkVars}
      ${focusVars}
      ${buttonVars}
      ${secondaryButtonVars}
      ${layoutVars}
      ${gradientVars}
      ${heroVars}
      ${patternVars}
    }
    
    /* Global body styles */
    body {
      background-color: var(--brand-background);
      color: var(--brand-text-body);
      font-family: var(--brand-font-body);
      transition: background-color 0.2s ease, color 0.2s ease;
    }
    
    /* Headings use brand heading font */
    h1, h2, h3, h4, h5, h6 {
      font-family: var(--brand-font-heading);
      color: var(--brand-text-primary);
    }
    ${linkStyles}
    ${focusStyles}
    ${buttonStyles}
    
    /* Custom brand CSS */
    ${brand.customCss || ''}
  `
}

// ============================================================================
// Provider Component
// ============================================================================

interface BrandedThemeProviderProps {
  children: ReactNode
  defaultBrandId?: string
  defaultColorMode?: EuiThemeColorMode
}

// API Brand type (simplified version from backend)
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

// Convert API brand to full BrandTheme
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

export function BrandedThemeProvider({ 
  children,
  defaultBrandId,
  defaultColorMode = 'light',
}: BrandedThemeProviderProps) {
  // Initialize brand from URL/localStorage
  const [brandId, setBrandId] = useState<string>(() => {
    return defaultBrandId || getSelectedBrandId()
  })
  
  // Track all brands (static + API)
  const [allBrands, setAllBrands] = useState<Record<string, BrandTheme>>(staticBrands)
  
  // Initialize color mode from localStorage/system preference
  const [colorMode, setColorMode] = useState<EuiThemeColorMode>(() => {
    const saved = localStorage.getItem('eui-theme') as EuiThemeColorMode | null
    if (saved === 'light' || saved === 'dark') return saved
    
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }
    return defaultColorMode
  })
  
  // Fetch brands from API and merge with static brands
  const refreshBrands = useCallback(async () => {
    try {
      const response = await fetch('/api/branding/')
      if (response.ok) {
        const apiBrands: ApiBrand[] = await response.json()
        
        // Merge API brands with static brands (static themes take priority)
        const merged = { ...staticBrands }
        for (const apiBrand of apiBrands) {
          // Only add if not already in static brands
          if (!staticBrands[apiBrand.id]) {
            const theme = apiBrandToTheme(apiBrand)
            merged[apiBrand.id] = theme
            addBrand(theme) // Also add to in-memory registry for other components
          }
        }
        setAllBrands(merged)
      }
    } catch {
      // API not available, use static brands only
      console.log('Brand API not available, using static brands')
    }
  }, [])
  
  // Fetch brands on mount
  useEffect(() => {
    refreshBrands()
  }, [refreshBrands])
  
  const brand = allBrands[brandId] || allBrands.default || staticBrands.default
  const availableBrands = Object.values(allBrands)
  
  // Inject CSS variables when brand or color mode changes
  useEffect(() => {
    const styleId = 'branded-theme-variables'
    let styleEl = document.getElementById(styleId) as HTMLStyleElement | null
    
    if (!styleEl) {
      styleEl = document.createElement('style')
      styleEl.id = styleId
      document.head.appendChild(styleEl)
    }
    
    styleEl.textContent = generateCssVariables(brand, colorMode)

    // Inject @font-face declarations
    const fontStyleId = 'branded-theme-fontfaces'
    let fontStyleEl = document.getElementById(fontStyleId) as HTMLStyleElement | null
    if (brand.fontFaces && brand.fontFaces.length > 0) {
      if (!fontStyleEl) {
        fontStyleEl = document.createElement('style')
        fontStyleEl.id = fontStyleId
        document.head.appendChild(fontStyleEl)
      }
      fontStyleEl.textContent = brand.fontFaces.map(ff => `
        @font-face {
          font-family: '${ff.family}';
          src: ${ff.src};
          font-weight: ${ff.weight || 'normal'};
          font-style: ${ff.style || 'normal'};
          font-display: ${ff.display || 'swap'};
        }
      `).join('\n')
    } else if (fontStyleEl) {
      fontStyleEl.textContent = ''
    }

    // Update favicon
    if (brand.favicon) {
      let faviconEl = document.querySelector('link[rel="icon"]') as HTMLLinkElement | null
      if (!faviconEl) {
        faviconEl = document.createElement('link')
        faviconEl.rel = 'icon'
        document.head.appendChild(faviconEl)
      }
      faviconEl.href = brand.favicon
    }

    // Set data attributes for CSS targeting
    document.body.setAttribute('data-brand', brandId)
    document.body.setAttribute('data-theme', colorMode)
    document.documentElement.classList.toggle('dark', colorMode === 'dark')
  }, [brand, brandId, colorMode])
  
  // Persist color mode
  useEffect(() => {
    localStorage.setItem('eui-theme', colorMode)
  }, [colorMode])
  
  const toggleColorMode = () => {
    setColorMode(prev => prev === 'light' ? 'dark' : 'light')
  }
  
  const setBrand = (newBrandId: string) => {
    // Set the brand ID - if it doesn't exist, the fallback in `brand` will handle it
    setBrandId(newBrandId)
    persistBrand(newBrandId)
  }
  
  const contextValue: BrandedThemeContextType = {
    colorMode,
    setColorMode,
    toggleColorMode,
    brand,
    brandId,
    setBrand,
    availableBrands,
    refreshBrands,
  }
  
  return (
    <BrandedThemeContext.Provider value={contextValue}>
      <EuiProvider colorMode={colorMode} cache={euiCache}>
        {children}
      </EuiProvider>
    </BrandedThemeContext.Provider>
  )
}

