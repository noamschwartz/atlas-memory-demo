import React, { useState, useEffect, createContext, useContext } from 'react'
import { EuiProvider, EuiThemeColorMode } from '@elastic/eui'
import createCache from '@emotion/cache'

/**
 * EUI Provider Wrapper for Vite
 * 
 * MUCH SIMPLER than Next.js version:
 * - No SSR hydration workarounds needed
 * - No 'use client' directives
 * - No mounted state checks
 * 
 * Vite is client-only, so EUI works naturally.
 */

// Create Emotion cache for EUI styles
const euiCache = createCache({
  key: 'eui',
  container: document.head,
})
euiCache.compat = true

interface ThemeContextType {
  colorMode: EuiThemeColorMode
  setColorMode: (mode: EuiThemeColorMode) => void
  toggleColorMode: () => void
}

const ThemeContext = createContext<ThemeContextType>({
  colorMode: 'light',
  setColorMode: () => {},
  toggleColorMode: () => {},
})

export function useTheme() {
  return useContext(ThemeContext)
}

interface EuiProviderWrapperProps {
  children: React.ReactNode
  initialColorMode?: EuiThemeColorMode
}

export function EuiProviderWrapper({ 
  children, 
  initialColorMode = 'light' 
}: EuiProviderWrapperProps) {
  const [colorMode, setColorMode] = useState<EuiThemeColorMode>(() => {
    // Check localStorage on init (client-only, so this is safe)
    const saved = localStorage.getItem('eui-theme') as EuiThemeColorMode | null
    if (saved === 'light' || saved === 'dark') return saved
    
    // Check system preference
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }
    return initialColorMode
  })

  // Persist theme changes
  useEffect(() => {
    localStorage.setItem('eui-theme', colorMode)
    document.documentElement.classList.toggle('dark', colorMode === 'dark')
  }, [colorMode])

  const toggleColorMode = () => {
    setColorMode(prev => prev === 'light' ? 'dark' : 'light')
  }

  return (
    <ThemeContext.Provider value={{ colorMode, setColorMode, toggleColorMode }}>
      <EuiProvider colorMode={colorMode} cache={euiCache}>
        {children}
      </EuiProvider>
    </ThemeContext.Provider>
  )
}
