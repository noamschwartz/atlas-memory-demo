/**
 * Date formatting utilities for consistent date display across the application
 */

/**
 * Format date for conversation list display (short format)
 * @param dateStr - ISO date string
 * @returns Formatted date string (e.g., "Dec 10, 2:30 PM")
 */
export function formatShortDate(dateStr: string): string {
  if (!dateStr) return 'Invalid date'
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return 'Invalid date'
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Format date for conversation detail display (full format)
 * @param dateStr - ISO date string
 * @returns Formatted date string (e.g., "12/10/2024, 2:30:45 PM")
 */
export function formatFullDate(dateStr: string): string {
  if (!dateStr) return 'Invalid date'
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return 'Invalid date'
  return date.toLocaleString()
}



