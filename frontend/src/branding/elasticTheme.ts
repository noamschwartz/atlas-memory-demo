/**
 * Elastic Brand Theme
 * 
 * Official Elastic branding colors and styling
 * This is the default theme for the Agent Starter template
 * 
 * Brand Guidelines Reference: https://brand.elastic.co
 */

export const elasticBranding = {
  name: 'Lumio Support Demo',
  sourceUrl: 'https://www.elastic.co',
  extractedAt: '2025-12-11',
  
  // Official Elastic brand colors
  colors: {
    primary: '#07C',        // Elastic Blue - primary brand color
    accent: '#00BFB3',      // Elastic Teal - accent/success color  
    secondary: '#F04E98',   // Elastic Pink - secondary accent
    darkBlue: '#003366',    // Dark blue for headers/emphasis
    background: '#F5F7FA',  // EUI default background
    white: '#FFFFFF',       // Cards, content areas
    black: '#1A1C21',       // Rich black for text
    textPrimary: '#343741', // EUI text color
    textBody: '#69707D',    // EUI subdued text
    border: '#D3DAE6',      // EUI borders
    // Additional Elastic palette
    success: '#00BFB3',     // Teal
    warning: '#FEC514',     // Yellow
    danger: '#BD271E',      // Red
  },
  
  // Typography - EUI uses Inter by default
  fonts: {
    heading: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    body: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fallback: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  
  // Spacing - EUI defaults
  spacing: {
    borderRadius: '6px',
    borderRadiusSmall: '4px',
  },
  
  // Official Elasticsearch logo (colorful version)
  // Source: https://cdn.worldvectorlogo.com/logos/elasticsearch.svg
  logo: {
    svgDataUrl: `data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M255.96 134.393c0-21.521-13.373-40.117-33.223-47.43a75.239 75.239 0 0 0 1.253-13.791c0-39.909-32.386-72.295-72.295-72.295-23.193 0-44.923 11.074-58.505 30.088-6.686-5.224-14.835-7.94-23.402-7.94-21.104 0-38.446 17.133-38.446 38.446 0 4.597.836 9.194 2.298 13.373C13.582 81.739 0 100.962 0 122.274c0 21.522 13.373 40.327 33.431 47.64-.835 4.388-1.253 8.985-1.253 13.79 0 39.7 32.386 72.087 72.086 72.087 23.402 0 44.924-11.283 58.505-30.088 6.686 5.223 15.044 8.149 23.611 8.149 21.104 0 38.446-17.134 38.446-38.446 0-4.597-.836-9.194-2.298-13.373 19.64-7.104 33.431-26.327 33.431-47.64z' fill='%23FFF'/%3E%3Cpath d='M100.085 110.364l57.043 26.119 57.669-50.565a64.312 64.312 0 0 0 1.253-12.746c0-35.52-28.834-64.355-64.355-64.355-21.313 0-41.162 10.447-53.072 27.998l-9.612 49.73 11.074 23.82z' fill='%23F4BD19'/%3E%3Cpath d='M40.953 170.75c-.835 4.179-1.253 8.567-1.253 12.955 0 35.52 29.043 64.564 64.564 64.564 21.522 0 41.372-10.656 53.49-28.208l9.403-49.729-12.746-24.238-57.251-26.118-56.207 50.774z' fill='%233CBEB1'/%3E%3Cpath d='M40.536 71.918l39.073 9.194 8.775-44.506c-5.432-4.179-11.91-6.268-18.805-6.268-16.925 0-30.924 13.79-30.924 30.924 0 3.552.627 7.313 1.88 10.656z' fill='%23E9478C'/%3E%3Cpath d='M37.192 81.32c-17.551 5.642-29.67 22.567-29.67 40.954 0 17.97 11.074 34.059 27.79 40.327l54.953-49.73-10.03-21.52-43.043-10.03z' fill='%232C458F'/%3E%3Cpath d='M167.784 219.852c5.432 4.18 11.91 6.478 18.596 6.478 16.925 0 30.924-13.79 30.924-30.924 0-3.761-.627-7.314-1.88-10.657l-39.073-9.193-8.567 44.296z' fill='%2395C63D'/%3E%3Cpath d='M175.724 165.317l43.043 10.03c17.551-5.85 29.67-22.566 29.67-40.954 0-17.97-11.074-33.849-27.79-40.326l-56.415 49.311 11.492 21.94z' fill='%23176655'/%3E%3C/svg%3E`,
    alt: 'Elastic',
  },
  
  // Same logo for light backgrounds (it has white background built in)
  logoDark: {
    svgDataUrl: `data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M255.96 134.393c0-21.521-13.373-40.117-33.223-47.43a75.239 75.239 0 0 0 1.253-13.791c0-39.909-32.386-72.295-72.295-72.295-23.193 0-44.923 11.074-58.505 30.088-6.686-5.224-14.835-7.94-23.402-7.94-21.104 0-38.446 17.133-38.446 38.446 0 4.597.836 9.194 2.298 13.373C13.582 81.739 0 100.962 0 122.274c0 21.522 13.373 40.327 33.431 47.64-.835 4.388-1.253 8.985-1.253 13.79 0 39.7 32.386 72.087 72.086 72.087 23.402 0 44.924-11.283 58.505-30.088 6.686 5.223 15.044 8.149 23.611 8.149 21.104 0 38.446-17.134 38.446-38.446 0-4.597-.836-9.194-2.298-13.373 19.64-7.104 33.431-26.327 33.431-47.64z' fill='%23FFF'/%3E%3Cpath d='M100.085 110.364l57.043 26.119 57.669-50.565a64.312 64.312 0 0 0 1.253-12.746c0-35.52-28.834-64.355-64.355-64.355-21.313 0-41.162 10.447-53.072 27.998l-9.612 49.73 11.074 23.82z' fill='%23F4BD19'/%3E%3Cpath d='M40.953 170.75c-.835 4.179-1.253 8.567-1.253 12.955 0 35.52 29.043 64.564 64.564 64.564 21.522 0 41.372-10.656 53.49-28.208l9.403-49.729-12.746-24.238-57.251-26.118-56.207 50.774z' fill='%233CBEB1'/%3E%3Cpath d='M40.536 71.918l39.073 9.194 8.775-44.506c-5.432-4.179-11.91-6.268-18.805-6.268-16.925 0-30.924 13.79-30.924 30.924 0 3.552.627 7.313 1.88 10.656z' fill='%23E9478C'/%3E%3Cpath d='M37.192 81.32c-17.551 5.642-29.67 22.567-29.67 40.954 0 17.97 11.074 34.059 27.79 40.327l54.953-49.73-10.03-21.52-43.043-10.03z' fill='%232C458F'/%3E%3Cpath d='M167.784 219.852c5.432 4.18 11.91 6.478 18.596 6.478 16.925 0 30.924-13.79 30.924-30.924 0-3.761-.627-7.314-1.88-10.657l-39.073-9.193-8.567 44.296z' fill='%2395C63D'/%3E%3Cpath d='M175.724 165.317l43.043 10.03c17.551-5.85 29.67-22.566 29.67-40.954 0-17.97-11.074-33.849-27.79-40.326l-56.415 49.311 11.492 21.94z' fill='%23176655'/%3E%3C/svg%3E`,
    alt: 'Elastic',
  },
}

/**
 * EUI Theme Modifications for Elastic Branding
 * 
 * These overrides keep the EUI defaults but ensure brand consistency
 */
export const elasticEuiTheme = {
  colors: {
    LIGHT: {
      primary: elasticBranding.colors.primary,
      accent: elasticBranding.colors.accent,
      success: elasticBranding.colors.success,
    },
    DARK: {
      primary: elasticBranding.colors.primary,
      accent: elasticBranding.colors.accent,
      success: elasticBranding.colors.success,
    },
  },
}

/**
 * CSS Custom Properties for Elastic Branding
 * 
 * Inject these into the document for use in custom styles
 */
export const elasticCssVariables = `
  :root {
    --elastic-primary: ${elasticBranding.colors.primary};
    --elastic-accent: ${elasticBranding.colors.accent};
    --elastic-secondary: ${elasticBranding.colors.secondary};
    --elastic-dark-blue: ${elasticBranding.colors.darkBlue};
    --elastic-background: ${elasticBranding.colors.background};
    --elastic-white: ${elasticBranding.colors.white};
    --elastic-black: ${elasticBranding.colors.black};
    --elastic-text-primary: ${elasticBranding.colors.textPrimary};
    --elastic-text-body: ${elasticBranding.colors.textBody};
    --elastic-border: ${elasticBranding.colors.border};
    --elastic-border-radius: ${elasticBranding.spacing.borderRadius};
  }
`

