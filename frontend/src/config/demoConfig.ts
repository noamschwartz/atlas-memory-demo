/**
 * Demo Configuration
 *
 * Controls which pages are visible, demo metadata, and presentation settings.
 * The build process customizes this file for each demo.
 *
 * CUSTOMIZE THIS FILE for your specific demo!
 */

import type { NavLayoutConfig } from '../components/layout/navigationConfig'

// =============================================================================
// Navigation - which pages to show
// =============================================================================

/**
 * Two-tier navigation layout (recommended).
 *
 * - main:   pages shown directly in the menu, in display order
 * - more:   pages under a "More pages" submenu (null = auto-include all remaining)
 * - hidden: pages removed from navigation entirely (still routable by URL)
 *
 * Set to null to fall back to NAV_PAGES or show everything flat.
 *
 * Example configurations:
 *
 *   // Search-focused story with everything else in submenu
 *   { main: ['/', '/guide', '/search'], more: null, hidden: [] }
 *
 *   // Agent-focused story, hide search entirely
 *   { main: ['/', '/guide', '/chat', '/audit'], more: null, hidden: ['/search'] }
 *
 *   // All pages flat (no submenu) — same as null
 *   null
 */
export const NAV_LAYOUT: NavLayoutConfig | null = null

/**
 * Legacy: flat page whitelist.
 * Ignored when NAV_LAYOUT is set. Kept for backward compatibility.
 * Set to an array of paths to show only those pages, or null for all.
 */
export const NAV_PAGES: string[] | null = null

// =============================================================================
// Demo metadata - shown on the Guide page
// =============================================================================

/**
 * Demo title and subtitle for the Guide page header.
 * Set to null to use the default template values.
 */
export const DEMO_TITLE: string | null = null
export const DEMO_SUBTITLE: string | null = null
