import { EuiButtonIcon, EuiToolTip } from '@elastic/eui'
import { useTheme } from '../providers/BrandedThemeProvider'

/**
 * Theme Toggle Component
 * 
 * Simple dark/light mode toggle button.
 * Uses BrandedThemeProvider for theme state management.
 */
export function ThemeToggle() {
  const { colorMode, toggleColorMode } = useTheme()
  const isDark = colorMode === 'dark'

  return (
    <EuiToolTip content={isDark ? 'Light mode' : 'Dark mode'}>
      <EuiButtonIcon
        iconType={isDark ? 'sun' : 'moon'}
        onClick={toggleColorMode}
        aria-label="Toggle theme"
      />
    </EuiToolTip>
  )
}
