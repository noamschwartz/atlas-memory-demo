/**
 * Type declarations for EUI internal modules
 * 
 * These modules are used for the icon cache but don't have proper type exports.
 */

declare module '@elastic/eui/es/components/icon/icon' {
  export function appendIconComponentCache(icons: Record<string, any>): void
}

declare module '@elastic/eui/es/components/icon/assets/*' {
  export const icon: any
}


