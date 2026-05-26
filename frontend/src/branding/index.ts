/**
 * Multi-Brand Theme Management
 * 
 * Allows storing multiple customer brandings and switching between them.
 * Brands can be selected via URL parameter (?brand=mybrand) or programmatically.
 * 
 * To add a new brand:
 * 1. Create a theme file: [brandName]Theme.ts (see exampleTheme.ts for reference)
 * 2. Export a [brandName]Branding object with the required structure
 * 3. The brand will be automatically discovered and registered!
 * 
 * For testing/demo themes that shouldn't be committed:
 * - Prefix the filename with "testing": testingGovukTheme.ts, testingAcmeTheme.ts
 * - These are gitignored but still auto-loaded for local development
 * - The "testing" prefix is stripped from the brand ID (e.g., testingGovuk -> govuk)
 * 
 * Theme files are auto-imported from this directory using Vite's import.meta.glob.
 * Files matching *Theme.ts pattern are automatically loaded (except exampleTheme.ts).
 */

// ============================================================================
// Brand Type Definition
// ============================================================================

// ============================================================================
// Component Style Types
// ============================================================================

/** Link styling configuration */
export interface BrandLinkStyle {
  color: string
  hoverColor?: string
  /** Underline thickness (e.g., "1px", "max(1px, .0625rem)") */
  underlineThickness?: string
  /** Underline offset from text */
  underlineOffset?: string
  /** Focus state configuration */
  focus?: {
    backgroundColor?: string
    /** Box shadow for focus ring */
    boxShadow?: string
    /** Whether to remove underline on focus */
    removeUnderline?: boolean
  }
}

/** Focus ring configuration for accessibility */
export interface BrandFocusRing {
  /** Focus ring color (e.g., "#FFDD00" for gov.uk yellow) */
  color: string
  /** Focus ring width */
  width?: string
  /** Focus ring offset from element */
  offset?: string
  /** Additional box-shadow for focus states */
  boxShadow?: string
}

/** Button variant styling */
export interface BrandButtonStyle {
  backgroundColor: string
  textColor: string
  /** Border radius (overrides global if set) */
  borderRadius?: string
  /** Box shadow (e.g., "0 2px 0 #002d18" for gov.uk) */
  boxShadow?: string
  /** Border style */
  border?: string
  /** Padding */
  padding?: string
  /** Font weight */
  fontWeight?: string
  /** Hover state */
  hover?: {
    backgroundColor?: string
    textColor?: string
    boxShadow?: string
  }
  /** Focus state */
  focus?: {
    boxShadow?: string
    outline?: string
  }
}

/** Layout constraints */
export interface BrandLayout {
  /** Maximum content width (e.g., "960px" for gov.uk) */
  maxWidth?: string
  /** Container padding */
  containerPadding?: string
  /** Section spacing */
  sectionSpacing?: string
  /** Header height (e.g., "60px" for gov.uk) */
  headerHeight?: string
}

/** Gradient configuration for brand visual identity */
export interface BrandGradients {
  /** Primary brand gradient (e.g., "linear-gradient(135deg, #360065 0%, #6B21A8 100%)") */
  primary?: string
  /** Accent/secondary gradient */
  accent?: string
  /** Hero section gradient overlay */
  hero?: string
}

/** Hero image configuration */
export interface BrandHeroImage {
  /** Image URL — local (/brands/ifs/images/hero.jpg) or external */
  url: string
  alt?: string
  /** CSS background-position (default: "center") */
  position?: string
  /** CSS overlay color (e.g., "rgba(54, 0, 101, 0.7)") */
  overlay?: string
}

/** @font-face declaration for custom font loading */
export interface BrandFontFace {
  /** Font family name (must match fonts.heading or fonts.body reference) */
  family: string
  /** CSS src value — url() format (e.g., "url('/brands/ifs/fonts/euclid.woff2') format('woff2')") */
  src: string
  /** Font weight or range (e.g., "400", "400 700") */
  weight?: string
  /** Font style (e.g., "normal", "italic") */
  style?: string
  /** Font-display strategy (default: "swap") */
  display?: string
}

// ============================================================================
// Main Brand Theme Type
// ============================================================================

export interface BrandTheme {
  id: string
  name: string
  sourceUrl: string
  extractedAt: string
  colors: {
    primary: string
    accent: string
    background: string
    white: string
    black: string
    textPrimary: string
    textBody: string
    border: string
    [key: string]: string  // Allow additional colors
  }
  /** Optional: Dark mode color overrides */
  colorsDark?: Partial<BrandTheme['colors']>
  fonts: {
    heading: string
    body: string
    fallback: string
  }
  spacing: {
    borderRadius: string
    borderRadiusSmall: string
  }
  logo: {
    /** SVG data URL (e.g., "data:image/svg+xml,...") - for embedded logos */
    svgDataUrl?: string
    /** Image URL (e.g., "https://example.com/logo.svg") - for external logos */
    url?: string
    alt: string
    /** If true, logo already contains brand text - don't show brand name separately */
    logoContainsText?: boolean
  }
  /** Optional: Dark variant of logo for light backgrounds */
  logoDark?: {
    svgDataUrl?: string
    url?: string
    alt: string
  }
  
  // ============================================================================
  // Extended Branding (Tier 1-3)
  // ============================================================================
  
  /** Link styling - color, underline, hover, focus */
  links?: BrandLinkStyle
  
  /** Focus ring styling for accessibility */
  focusRing?: BrandFocusRing
  
  /** Button variants */
  buttons?: {
    primary?: BrandButtonStyle
    secondary?: BrandButtonStyle
    /** Warning/destructive button style */
    warning?: BrandButtonStyle
  }
  
  /** Layout constraints */
  layout?: BrandLayout
  
  /**
   * Custom CSS to inject for brand-specific overrides.
   * Use sparingly - prefer structured properties above.
   * This CSS is injected globally when the brand is active.
   *
   * @example
   * customCss: `
   *   .govuk-tag { text-transform: uppercase; letter-spacing: 1px; }
   *   .govuk-inset-text { border-left: 10px solid var(--brand-border); }
   * `
   */
  customCss?: string

  // ============================================================================
  // Visual Fidelity (Tier 4 — Gradients, Imagery, Fonts)
  // ============================================================================

  /** Brand gradients — signature visual identity element for many modern brands */
  gradients?: BrandGradients

  /** Hero image for landing/feature pages */
  heroImage?: BrandHeroImage

  /** Background pattern (CSS background value — url or repeating pattern) */
  backgroundPattern?: string

  /**
   * @font-face declarations for custom font loading.
   * Fonts should be hosted locally in /brands/[brandId]/fonts/ to avoid CORS.
   */
  fontFaces?: BrandFontFace[]

  /** Favicon URL — replaces default when brand is active */
  favicon?: string
}

// ============================================================================
// Auto-Discovery: Import all theme files
// ============================================================================

/**
 * Automatically discover and import all theme files matching *Theme.ts pattern
 * This makes the template more robust - just create a theme file and it's registered!
 * 
 * Uses Vite's import.meta.glob for dynamic imports at build time.
 */
const themeModules = import.meta.glob('./*Theme.ts', { 
  eager: true,
}) as Record<string, { [key: string]: any }>

// ============================================================================
// Helper: Convert branding object to BrandTheme
// ============================================================================

function brandingToTheme(
  branding: any,
  brandId: string,
  sourceUrl: string = '',
  extractedAt: string = ''
): BrandTheme {
  return {
    id: brandId,
    name: branding.name || brandId.charAt(0).toUpperCase() + brandId.slice(1),
    sourceUrl: branding.sourceUrl || sourceUrl,
    extractedAt: branding.extractedAt || extractedAt,
    colors: {
      primary: branding.colors.primary,
      accent: branding.colors.accent,
      background: branding.colors.background,
      white: branding.colors.white,
      black: branding.colors.black,
      textPrimary: branding.colors.textPrimary,
      textBody: branding.colors.textBody,
      border: branding.colors.border,
      ...branding.colors, // Include any additional colors
    },
    colorsDark: branding.colorsDark,
    fonts: {
      heading: branding.fonts.heading,
      body: branding.fonts.body,
      fallback: branding.fonts.fallback,
    },
    spacing: {
      borderRadius: branding.spacing.borderRadius,
      borderRadiusSmall: branding.spacing.borderRadiusSmall,
    },
    logo: branding.logo || { svgDataUrl: '', alt: brandId },
    logoDark: branding.logoDark,
    // Extended branding (Tier 1-3)
    links: branding.links,
    focusRing: branding.focusRing,
    buttons: branding.buttons,
    layout: branding.layout,
    customCss: branding.customCss,
    // Visual fidelity (Tier 4)
    gradients: branding.gradients,
    heroImage: branding.heroImage,
    backgroundPattern: branding.backgroundPattern,
    fontFaces: branding.fontFaces,
    favicon: branding.favicon,
  }
}

// ============================================================================
// Available Brands Registry
// ============================================================================

// Start with default theme - using Elastic branding
const brandsRegistry: Record<string, BrandTheme> = {
  // Default theme - Official Elastic branding
  default: {
    id: 'default',
    name: 'Elastic Agent Starter',
    sourceUrl: 'https://www.elastic.co',
    extractedAt: '2025-12-11',
    colors: {
      primary: '#07C',        // Elastic Blue
      accent: '#00BFB3',      // Elastic Teal
      background: '#F5F7FA',  // EUI default
      white: '#FFFFFF',
      black: '#1A1C21',
      textPrimary: '#343741',
      textBody: '#69707D',
      border: '#D3DAE6',
    },
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
      // Official Elasticsearch logo - Source: https://cdn.worldvectorlogo.com/logos/elasticsearch.svg
      svgDataUrl: `data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M255.96 134.393c0-21.521-13.373-40.117-33.223-47.43a75.239 75.239 0 0 0 1.253-13.791c0-39.909-32.386-72.295-72.295-72.295-23.193 0-44.923 11.074-58.505 30.088-6.686-5.224-14.835-7.94-23.402-7.94-21.104 0-38.446 17.133-38.446 38.446 0 4.597.836 9.194 2.298 13.373C13.582 81.739 0 100.962 0 122.274c0 21.522 13.373 40.327 33.431 47.64-.835 4.388-1.253 8.985-1.253 13.79 0 39.7 32.386 72.087 72.086 72.087 23.402 0 44.924-11.283 58.505-30.088 6.686 5.223 15.044 8.149 23.611 8.149 21.104 0 38.446-17.134 38.446-38.446 0-4.597-.836-9.194-2.298-13.373 19.64-7.104 33.431-26.327 33.431-47.64z' fill='%23FFF'/%3E%3Cpath d='M100.085 110.364l57.043 26.119 57.669-50.565a64.312 64.312 0 0 0 1.253-12.746c0-35.52-28.834-64.355-64.355-64.355-21.313 0-41.162 10.447-53.072 27.998l-9.612 49.73 11.074 23.82z' fill='%23F4BD19'/%3E%3Cpath d='M40.953 170.75c-.835 4.179-1.253 8.567-1.253 12.955 0 35.52 29.043 64.564 64.564 64.564 21.522 0 41.372-10.656 53.49-28.208l9.403-49.729-12.746-24.238-57.251-26.118-56.207 50.774z' fill='%233CBEB1'/%3E%3Cpath d='M40.536 71.918l39.073 9.194 8.775-44.506c-5.432-4.179-11.91-6.268-18.805-6.268-16.925 0-30.924 13.79-30.924 30.924 0 3.552.627 7.313 1.88 10.656z' fill='%23E9478C'/%3E%3Cpath d='M37.192 81.32c-17.551 5.642-29.67 22.567-29.67 40.954 0 17.97 11.074 34.059 27.79 40.327l54.953-49.73-10.03-21.52-43.043-10.03z' fill='%232C458F'/%3E%3Cpath d='M167.784 219.852c5.432 4.18 11.91 6.478 18.596 6.478 16.925 0 30.924-13.79 30.924-30.924 0-3.761-.627-7.314-1.88-10.657l-39.073-9.193-8.567 44.296z' fill='%2395C63D'/%3E%3Cpath d='M175.724 165.317l43.043 10.03c17.551-5.85 29.67-22.566 29.67-40.954 0-17.97-11.074-33.849-27.79-40.326l-56.415 49.311 11.492 21.94z' fill='%23176655'/%3E%3C/svg%3E`,
      alt: 'Elastic',
    },
  },
}

// Auto-register all discovered theme files
for (const [path, module] of Object.entries(themeModules)) {
  // Skip example theme and elasticTheme (elasticTheme is already the default)
  if (path.includes('exampleTheme') || path.includes('elasticTheme')) {
    continue
  }
  
  // Extract brand ID from filename: ./customTheme.ts -> custom
  // Strip "testing" prefix if present: ./testingGovukTheme.ts -> govuk
  let filename = path.replace('./', '').replace('Theme.ts', '')
  if (filename.toLowerCase().startsWith('testing')) {
    filename = filename.slice(7) // Remove "testing" prefix
  }
  const brandId = filename.toLowerCase()
  
  // Find the branding export (could be customBranding, myBrandBranding, etc.)
  // For testing files, the export is still named after the brand (e.g., govukBranding)
  const moduleExports = module as { [key: string]: any }
  const brandingKey = Object.keys(moduleExports).find(key => 
    key.toLowerCase().includes('branding') || 
    key.toLowerCase().includes(brandId)
  )
  
  if (brandingKey && moduleExports[brandingKey]) {
    const branding = moduleExports[brandingKey]
    
    // Extract metadata from branding object or use defaults
    const sourceUrl = branding.sourceUrl || ''
    const extractedAt = branding.extractedAt || new Date().toISOString().split('T')[0]
    
    try {
      brandsRegistry[brandId] = brandingToTheme(branding, brandId, sourceUrl, extractedAt)
      console.log(`✅ Auto-registered brand: ${brandId}`)
    } catch (error) {
      console.warn(`⚠️ Failed to register brand ${brandId} from ${path}:`, error)
    }
  } else {
    console.warn(`⚠️ No branding export found in ${path}. Expected export like "${brandId}Branding"`)
  }
}

export const brands: Record<string, BrandTheme> = brandsRegistry

// ============================================================================
// Brand Selection Utilities
// ============================================================================

/**
 * Get brand from URL parameter or localStorage
 */
export function getSelectedBrandId(): string {
  if (typeof window !== 'undefined') {
    // Check URL parameter first — and persist it so the brand "sticks"
    const params = new URLSearchParams(window.location.search)
    const urlBrand = params.get('brand')
    if (urlBrand && brands[urlBrand]) {
      localStorage.setItem('selected-brand', urlBrand)
      return urlBrand
    }

    // Check localStorage
    const storedBrand = localStorage.getItem('selected-brand')
    if (storedBrand && brands[storedBrand]) {
      return storedBrand
    }

    // If there's exactly one non-default brand, use it
    // (common case: demo has been customised for a single customer)
    const customBrands = Object.keys(brands).filter(id => id !== 'default')
    if (customBrands.length === 1) {
      return customBrands[0]
    }
  }

  return 'default'
}

/**
 * Get the currently selected brand theme
 */
export function getSelectedBrand(): BrandTheme {
  const brandId = getSelectedBrandId()
  return brands[brandId] || brands.default
}

/**
 * Set the active brand and persist to localStorage
 */
export function setSelectedBrand(brandId: string): void {
  if (brands[brandId]) {
    localStorage.setItem('selected-brand', brandId)
    // Update URL without reload
    const url = new URL(window.location.href)
    url.searchParams.set('brand', brandId)
    window.history.replaceState({}, '', url.toString())
  }
}

/**
 * Get list of all available brands
 */
export function getAvailableBrands(): BrandTheme[] {
  return Object.values(brands)
}

/**
 * Generate CSS variables for a brand
 */
export function generateBrandCssVariables(brand: BrandTheme): string {
  return `
    :root {
      --brand-primary: ${brand.colors.primary};
      --brand-accent: ${brand.colors.accent};
      --brand-background: ${brand.colors.background};
      --brand-white: ${brand.colors.white};
      --brand-black: ${brand.colors.black};
      --brand-text-primary: ${brand.colors.textPrimary};
      --brand-text-body: ${brand.colors.textBody};
      --brand-border: ${brand.colors.border};
      --brand-border-radius: ${brand.spacing.borderRadius};
      --brand-font-heading: ${brand.fonts.heading};
      --brand-font-body: ${brand.fonts.body};
    }
  `
}

// ============================================================================
// Add New Brand Helper
// ============================================================================

/**
 * Add a new brand to the registry (for runtime additions)
 * In production, this would save to a backend/database
 */
export function addBrand(brand: BrandTheme): void {
  brands[brand.id] = brand
  console.log(`Added brand: ${brand.name}`)
}
