/**
 * Simplified App Header for Starter Template
 * 
 * Clean header with:
 * - App logo/title
 * - Navigation menu
 * - Dark/light mode toggle
 * 
 * Removed features (see AppHeader.tsx for full version):
 * - Brand switcher
 * - Shopping cart with badge
 * - Dynamic brand theming
 */

import { useNavigate, useLocation } from 'react-router-dom'
import { useState } from 'react'
import {
  EuiHeader,
  EuiHeaderSection,
  EuiHeaderSectionItem,
  EuiPopover,
  EuiButtonIcon,
  EuiContextMenu,
  EuiIcon,
} from '@elastic/eui'
import { ThemeToggle } from './ThemeToggle'
import { getNavItems } from './navigationConfigSimple'

// App configuration - customize for your app
const APP_NAME = 'Search Demo'
const APP_PRIMARY_COLOR = '#0077cc'

export function AppHeaderSimple() {
  const navigate = useNavigate()
  const location = useLocation()
  const [isMenuOpen, setIsMenuOpen] = useState(false)

  const navItems = getNavItems()
  const currentPath = location.pathname

  return (
    <EuiHeader 
      position="fixed"
      style={{
        backgroundColor: APP_PRIMARY_COLOR,
        borderBottom: 'none',
      }}
    >
      <EuiHeaderSection grow={false}>
        <EuiHeaderSectionItem>
          <a 
            href="/"
            onClick={(e) => {
              e.preventDefault()
              navigate('/')
            }}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '12px',
              textDecoration: 'none',
              padding: '0 8px',
            }}
          >
            {/* App Logo - replace with your logo */}
            <div
              style={{
                width: '28px',
                height: '28px',
                backgroundColor: 'white',
                borderRadius: '4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: APP_PRIMARY_COLOR,
                fontSize: '14px',
                fontWeight: 700,
              }}
            >
              {APP_NAME.charAt(0)}
            </div>
            <span style={{ 
              color: 'white',
              fontWeight: 600,
              fontSize: '16px',
            }}>
              {APP_NAME}
            </span>
          </a>
        </EuiHeaderSectionItem>
      </EuiHeaderSection>

      <EuiHeaderSection side="right">
        <EuiHeaderSectionItem>
          <ThemeToggle />
        </EuiHeaderSectionItem>

        {/* Navigation Menu */}
        <EuiHeaderSectionItem>
          <EuiPopover
            button={
              <EuiButtonIcon
                iconType="menu"
                aria-label="Navigation menu"
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                size="s"
                style={{ color: 'white' }}
              />
            }
            isOpen={isMenuOpen}
            closePopover={() => setIsMenuOpen(false)}
            anchorPosition="downRight"
            panelPaddingSize="none"
          >
            <EuiContextMenu
              initialPanelId={0}
              panels={[
                {
                  id: 0,
                  items: navItems.map((item) => ({
                    name: item.label,
                    icon: <EuiIcon type={item.icon} />,
                    onClick: () => {
                      navigate(item.path)
                      setIsMenuOpen(false)
                    },
                    isSelected: currentPath === item.path,
                  })),
                },
              ]}
            />
          </EuiPopover>
        </EuiHeaderSectionItem>
      </EuiHeaderSection>
    </EuiHeader>
  )
}

