/**
 * Navigation Configuration
 * 
 * Centralized navigation menu configuration for consistent navigation
 * across all header components.
 * 
 * Features are grouped by category:
 * - demo: Features for building customer demos
 * - tools: Development and debugging tools
 * - advanced: Features requiring additional setup
 *
 * Navigation layout is controlled by NAV_LAYOUT in demoConfig.ts:
 * - main: pages shown directly in the menu
 * - more: pages in a "More pages" submenu (null = auto-populate remaining)
 * - hidden: pages excluded from navigation entirely (still routable by URL)
 */

export interface NavItem {
  path: string
  label: string
  icon: string
  description?: string
  category?: 'demo' | 'tools' | 'advanced'
  /** If true, requires Agent Builder connection */
  requiresAgent?: boolean
  /** If true, requires LLM proxy configuration */
  requiresLLMProxy?: boolean
}

/**
 * Two-tier navigation layout.
 *
 * Controls which pages appear in the main menu vs a "More pages" submenu.
 * Pages not listed in main/more/hidden are treated as if they were in `more`
 * when `more` is null (auto-populate), or hidden when `more` is explicit.
 *
 * @example
 * // Search-focused: main pages inline, everything else in submenu
 * { main: ['/', '/guide', '/search'], more: null, hidden: [] }
 *
 * @example
 * // Agent-focused, hide search
 * { main: ['/', '/guide', '/chat', '/audit'], more: null, hidden: ['/search'] }
 */
export interface NavLayoutConfig {
  /** Pages shown directly in the main navigation, in display order */
  main: string[]
  /** Pages in "More pages" submenu. null = auto-include all remaining pages. */
  more: string[] | null
  /** Pages hidden from navigation entirely (still accessible by URL) */
  hidden: string[]
}

/**
 * All available navigation items
 * 
 * Icons should be EUI icon names from:
 * https://eui.elastic.co/#/display/icons
 * 
 * To add a new feature:
 * 1. Add it here with appropriate category
 * 2. Add the route in App.tsx
 * 3. Add the page component
 * 4. (Optional) Add to WelcomePage FEATURES array for showcase
 */
export const NAV_ITEMS: NavItem[] = [
  // Home - always first
  {
    path: '/',
    label: 'Home',
    icon: 'home',
    description: 'Feature overview & setup guide',
  },
  {
    path: '/guide',
    label: 'Guide',
    icon: 'training',
    description: 'Demo guide with presenter notes',
  },
  {
    path: '/home',
    label: 'Store Home',
    icon: 'tag',
    description: 'Config-driven branded homepage',
    category: 'demo',
  },
  
  // Demo Building Features
  {
    path: '/atlas',
    label: 'Atlas Memory',
    icon: 'memory',
    description: 'Atlas — agent memory on Elasticsearch (chat + live inspector)',
    category: 'demo',
  },
  {
    path: '/chat',
    label: 'Chat',
    icon: 'newChat',
    description: 'Chat with your Agent Builder agent',
    category: 'demo',
    requiresAgent: true,
  },
  {
    path: '/branded',
    label: 'Demo',
    icon: 'sparkles',
    description: 'Branded demo experience',
    category: 'demo',
    requiresAgent: true,
  },
  {
    path: '/brands',
    label: 'Brands',
    icon: 'brush',
    description: 'Create and manage brand themes',
    category: 'demo',
  },
  {
    path: '/search',
    label: 'Search',
    icon: 'search',
    description: 'Product search with faceted filtering',
    category: 'demo',
  },
  {
    path: '/visual-search',
    label: 'Visual Search',
    icon: 'image',
    description: 'Text-to-image and image-to-image kNN search',
    category: 'demo',
  },
  {
    path: '/workflows',
    label: 'Workflows',
    icon: 'pipelineApp',
    description: 'Manage and run automated workflows',
    category: 'demo',
  },
  {
    path: '/geo',
    label: 'Geo Search',
    icon: 'mapMarker',
    description: 'Store finder with maps & delivery zones',
    category: 'demo',
  },
  {
    path: '/profile',
    label: 'Profile',
    icon: 'user',
    description: 'Demo persona and personalisation settings',
    category: 'demo',
  },
  {
    path: '/voice',
    label: 'Voice',
    icon: 'discuss',
    description: 'Voice-first chat with STT and TTS',
    category: 'demo',
    requiresAgent: true,
  },
  {
    path: '/overlay',
    label: 'Overlay Demo',
    icon: 'popout',
    description: 'Floating chat widget on sample content',
    category: 'demo',
    requiresAgent: true,
  },
  {
    path: '/overlay-guide',
    label: 'Inject Guide',
    icon: 'package',
    description: 'Inject chat onto any external website',
    category: 'demo',
  },
  
  // Development Tools
  {
    path: '/audit',
    label: 'Audit',
    icon: 'inspect',
    description: 'Review conversation history & reasoning',
    category: 'tools',
    requiresAgent: true,
  },
  {
    path: '/mcp',
    label: 'MCP',
    icon: 'plugs',
    description: 'Explore MCP server tools',
    category: 'tools',
    requiresAgent: true,
  },
  
  // Advanced Features
  {
    path: '/a2a-chat',
    label: 'A2A',
    icon: 'aggregate',
    description: 'Multi-agent orchestration',
    category: 'advanced',
    requiresAgent: true,
    requiresLLMProxy: true,
  },
]

/**
 * Get navigation items filtered by visibility
 * Some pages might want to hide certain nav items
 */
export function getNavItems(options?: {
  exclude?: string[]
  includeOnly?: string[]
  category?: NavItem['category']
}): NavItem[] {
  let items = NAV_ITEMS
  
  if (options?.category) {
    items = items.filter(item => item.category === options.category || item.path === '/')
  }
  
  if (options?.includeOnly) {
    items = items.filter(item => options.includeOnly!.includes(item.path))
  }
  
  if (options?.exclude) {
    items = items.filter(item => !options.exclude!.includes(item.path))
  }
  
  return items
}

/**
 * Get navigation items grouped by category
 */
export function getNavItemsByCategory(): Record<string, NavItem[]> {
  const grouped: Record<string, NavItem[]> = {
    home: [],
    demo: [],
    tools: [],
    advanced: [],
  }
  
  NAV_ITEMS.forEach(item => {
    if (item.path === '/') {
      grouped.home.push(item)
    } else if (item.category) {
      grouped[item.category].push(item)
    }
  })
  
  return grouped
}

/**
 * Get navigation items split into main and "more" tiers.
 *
 * Resolution order:
 * 1. If layout is provided, use its main/more/hidden config
 * 2. If layout is null but legacyNavPages is set, show only those pages (flat, no submenu)
 * 3. If both are null, show all pages flat
 *
 * @param layout - Two-tier layout config from demoConfig.ts, or null for flat nav
 * @param legacyNavPages - Legacy NAV_PAGES whitelist for backward compat, or null
 */
export function getNavLayout(
  layout: NavLayoutConfig | null,
  legacyNavPages: string[] | null,
): { main: NavItem[]; more: NavItem[] } {
  if (!layout) {
    const items = legacyNavPages
      ? NAV_ITEMS.filter(item => legacyNavPages.includes(item.path))
      : NAV_ITEMS
    return { main: items, more: [] }
  }

  const { main: mainPaths, more: morePaths, hidden } = layout
  const hiddenSet = new Set(hidden)
  const mainSet = new Set(mainPaths)

  const mainItems = mainPaths
    .map(path => NAV_ITEMS.find(item => item.path === path))
    .filter((item): item is NavItem => !!item)

  let moreItems: NavItem[]
  if (morePaths !== null) {
    moreItems = morePaths
      .map(path => NAV_ITEMS.find(item => item.path === path))
      .filter((item): item is NavItem => !!item)
  } else {
    moreItems = NAV_ITEMS.filter(
      item => !mainSet.has(item.path) && !hiddenSet.has(item.path),
    )
  }

  return { main: mainItems, more: moreItems }
}
