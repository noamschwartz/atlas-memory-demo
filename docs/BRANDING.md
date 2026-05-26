# Branding System Guide

Complete guide to adding and managing brand themes in the Elastic Agent Starter.

______________________________________________________________________

## Quick Start

To add a new brand theme:

1. **Create theme file**: `frontend/src/branding/[brandName]Theme.ts`
2. **Export branding object**: `export const [brandName]Branding = { ... }`
3. **Done!** The brand is automatically discovered and registered.

**Example:**

```typescript
// frontend/src/branding/myBrandTheme.ts
export const myBrandBranding = {
  colors: { primary: '#0077CC', ... },
  fonts: { heading: '...', ... },
  spacing: { borderRadius: '8px', ... },
  logo: { svgDataUrl: '...', alt: 'My Brand' },
}
```

The brand `mybrand` is now available immediately!

______________________________________________________________________

## How Auto-Discovery Works

The branding system uses **Vite's `import.meta.glob`** to automatically discover all theme files:

- **Pattern**: Files matching `*Theme.ts` in `frontend/src/branding/`
- **Excluded**: `exampleTheme.ts` (template file)
- **Registration**: Happens at build time - no runtime overhead
- **Console feedback**: Logs which brands were auto-registered

**Benefits:**

- ✅ No manual registration required
- ✅ Impossible to forget registration step
- ✅ Works seamlessly with merges and updates
- ✅ More robust template

______________________________________________________________________

## BrandTheme Interface

All brands must implement this TypeScript interface:

```typescript
interface BrandTheme {
  id: string           // Unique identifier (e.g., 'mybrand')
  name: string         // Display name (e.g., 'My Brand')
  sourceUrl: string    // Where branding was extracted from
  extractedAt: string  // Extraction date (ISO format)

  colors: {
    primary: string      // Main brand color (e.g., '#0077CC')
    accent: string       // Secondary color
    background: string   // Page background
    white: string        // Light surfaces
    black: string        // Dark text/elements
    textPrimary: string  // Heading text
    textBody: string     // Body text
    border: string       // Border color
    [key: string]: string  // Additional colors allowed
  }

  fonts: {
    heading: string    // Heading font stack
    body: string       // Body font stack
    fallback: string   // System fallback fonts
  }

  spacing: {
    borderRadius: string       // Standard radius (e.g., '8px')
    borderRadiusSmall: string  // Small radius (e.g., '4px')
  }

  logo: {
    svgDataUrl: string  // Base64 encoded SVG or data URL
    alt: string         // Alt text for accessibility
  }

  logoDark?: {          // Optional: dark variant for light backgrounds
    svgDataUrl: string
    alt: string
  }
}
```

______________________________________________________________________

## Creating a New Brand Theme

### Step 1: Copy the Template

```bash
cp frontend/src/branding/exampleTheme.ts frontend/src/branding/myBrandTheme.ts
```

### Step 2: Update the Export Name

The export name determines the brand ID:

```typescript
// File: myBrandTheme.ts
export const myBrandBranding = {  // ← Brand ID will be 'mybrand'
  // ... theme data
}
```

**Naming convention:**

- File: `[brandName]Theme.ts` (PascalCase)
- Export: `[brandName]Branding` (camelCase)
- Brand ID: `[brandname]` (lowercase, extracted from filename)

### Step 3: Fill in Brand Data

Use the template structure and fill in your brand's colors, fonts, spacing, and logo:

```typescript
export const myBrandBranding = {
  colors: {
    primary: '#0077CC',      // Main brand color
    accent: '#00BFB3',       // Secondary color
    background: '#F5F7FA',   // Page background
    white: '#FFFFFF',         // Light surfaces
    black: '#1A1C21',         // Dark text
    textPrimary: '#343741',   // Headings
    textBody: '#69707D',      // Body text
    border: '#D3DAE6',        // Borders
  },
  fonts: {
    heading: '"Inter", sans-serif',
    body: '"Inter", sans-serif',
    fallback: '-apple-system, BlinkMacSystemFont, sans-serif',
  },
  spacing: {
    borderRadius: '8px',
    borderRadiusSmall: '4px',
  },
  logo: {
    svgDataUrl: 'data:image/svg+xml,...',  // Your SVG logo
    alt: 'My Brand',
  },
}
```

### Step 4: Verify Auto-Registration

After creating the file, check the browser console when the app loads. You should see:

```text
✅ Auto-registered brand: mybrand
```

The brand is now available via:

- URL parameter: `?brand=mybrand`
- Programmatically: `setBrand('mybrand')`
- Brand switcher component

______________________________________________________________________

## Setting Default Brand

To make a brand the default (used when no brand is specified):

Edit `frontend/src/branding/index.ts`:

```typescript
export function getSelectedBrandId(): string {
  // ... existing logic ...
  return 'mybrand'  // ← Change this to your brand ID
}
```

Or set it in `frontend/src/main.tsx`:

```typescript
<BrandedThemeProvider defaultBrandId="mybrand">
  <App />
</BrandedThemeProvider>
```

______________________________________________________________________

## AI-Powered Brand Extraction

For production-quality branding, use AI to extract from a website:

```text
"Extract branding from https://customer-website.com and create a theme file"
```

The AI will:

1. Analyze the website's colors, fonts, and logo
2. Create `frontend/src/branding/[brandName]Theme.ts`
3. Export the branding object correctly
4. The brand is automatically registered!

See `hive-mind/patterns/branding/BRANDING_EXTRACTION_PATTERNS.md` for the full extraction guide.

______________________________________________________________________

## Using Branding in Components

### CSS Variables (Recommended)

Use CSS variables for automatic dark mode support:

```typescript
import { useBrand } from '../components/providers/BrandedThemeProvider'

function MyComponent() {
  const { brand } = useBrand()

  return (
    <div style={{
      backgroundColor: 'var(--brand-primary)',
      color: 'var(--brand-white)',
      fontFamily: 'var(--brand-font-heading)',
    }}>
      <img src={brand.logo.svgDataUrl} alt={brand.logo.alt} />
      <h1>{brand.name}</h1>
    </div>
  )
}
```

### Direct Access (When Needed)

Some components need actual hex values (e.g., `EuiAvatar`):

```typescript
import { useBrand } from '../components/providers/BrandedThemeProvider'

function MyComponent() {
  const { brand } = useBrand()

  return (
    <EuiAvatar
      name={brand.name}
      color={brand.colors.primary}  // Needs hex, not CSS variable
    />
  )
}
```

See `hive-mind/patterns/branding/COMPONENT_BRANDING_PATTERNS.md` for comprehensive component patterns.

______________________________________________________________________

## Available CSS Variables

The `BrandedThemeProvider` automatically injects these CSS variables:

| Variable                      | Description            | Light Mode              | Dark Mode               |
| ----------------------------- | ---------------------- | ----------------------- | ----------------------- |
| `--brand-primary`             | Primary brand color    | Brand primary           | Brand primary           |
| `--brand-accent`              | Secondary/accent color | Brand accent            | Brand accent            |
| `--brand-background`          | Page background        | Brand background        | `#1D1E24`               |
| `--brand-surface`             | Card/panel surfaces    | Brand white             | `#25262E`               |
| `--brand-white`               | Light surfaces         | Brand white             | `#25262E`               |
| `--brand-black`               | Dark text/elements     | Brand black             | `#FFFFFF`               |
| `--brand-text-primary`        | Headings               | Brand textPrimary       | `#FFFFFF`               |
| `--brand-text-body`           | Body text              | Brand textBody          | `#B4B7C1`               |
| `--brand-border`              | Borders                | Brand border            | `#404040`               |
| `--brand-border-radius`       | Standard radius        | Brand borderRadius      | Brand borderRadius      |
| `--brand-border-radius-small` | Small radius           | Brand borderRadiusSmall | Brand borderRadiusSmall |
| `--brand-font-heading`        | Heading font           | Brand fonts.heading     | Brand fonts.heading     |
| `--brand-font-body`           | Body font              | Brand fonts.body        | Brand fonts.body        |

______________________________________________________________________

## Brand Editor (Alternative Approach)

For quick demos, you can use the built-in Brand Editor:

1. Visit <http://localhost:3000/brands>
2. Create brands with color pickers
3. Upload logos for light/dark modes
4. Preview and switch between brands

Brands created via the editor are stored in `backend/data/brands.json` and loaded at runtime.

**Note:** Editor-created brands are separate from theme files. Theme files are preferred for production demos.

______________________________________________________________________

## Troubleshooting

### Brand Not Appearing

1. **Check export name**: Must be `[brandName]Branding` (camelCase)
2. **Check filename**: Must match `*Theme.ts` pattern
3. **Check console**: Look for registration messages or warnings
4. **Restart dev server**: Auto-discovery happens at build time

### Brand ID Mismatch

The brand ID is extracted from the filename:

- File: `customTheme.ts` → ID: `custom`
- File: `myBrandTheme.ts` → ID: `mybrand`

If you need a specific ID, rename the file accordingly.

### TypeScript Errors

Ensure your branding object matches the structure in `exampleTheme.ts`. The auto-discovery will warn if the structure is invalid.

______________________________________________________________________

## Best Practices

1. **Use exampleTheme.ts as template** - It has the correct structure
2. **Export naming**: `[brandName]Branding` (camelCase)
3. **File naming**: `[brandName]Theme.ts` (PascalCase)
4. **SVG logos**: Prefer SVG data URLs for best quality
5. **Test both modes**: Verify branding works in light and dark modes
6. **Document source**: Include `sourceUrl` and `extractedAt` for traceability

______________________________________________________________________

## Related Documentation

- `hive-mind/patterns/branding/BRANDING_EXTRACTION_PATTERNS.md` - AI extraction guide
- `hive-mind/patterns/branding/COMPONENT_BRANDING_PATTERNS.md` - Component usage patterns
- `frontend/src/branding/exampleTheme.ts` - Template file
- `frontend/src/branding/index.ts` - Auto-discovery implementation
