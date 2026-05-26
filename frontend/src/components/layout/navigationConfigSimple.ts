/**
 * Simplified Navigation Configuration for Starter Template
 * 
 * Basic navigation items for search application.
 * Customize this file to add your own navigation items.
 */

export interface NavItem {
  path: string
  label: string
  icon: string
  description?: string
}

/**
 * Navigation items for starter template
 * 
 * Default setup: Search + Analytics
 * Add your own items as needed.
 */
export const NAV_ITEMS: NavItem[] = [
  {
    path: '/search',
    label: 'Search',
    icon: 'search',
    description: 'Product search',
  },
  {
    path: '/analytics',
    label: 'Analytics',
    icon: 'stats',
    description: 'Search quality metrics',
  },
  {
    path: '/',
    label: 'Home',
    icon: 'home',
    description: 'Welcome page',
  },
]

/**
 * Get navigation items with optional filtering
 */
export function getNavItems(options?: {
  exclude?: string[]
  includeOnly?: string[]
}): NavItem[] {
  if (options?.includeOnly) {
    return NAV_ITEMS.filter(item => options.includeOnly!.includes(item.path))
  }
  
  if (options?.exclude) {
    return NAV_ITEMS.filter(item => !options.exclude!.includes(item.path))
  }
  
  return NAV_ITEMS
}

