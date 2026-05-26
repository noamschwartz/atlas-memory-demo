import { useNavigate } from 'react-router-dom'
import {
  EuiHeader,
  EuiHeaderSection,
  EuiHeaderSectionItem,
  EuiHeaderLink,
  EuiHeaderLinks,
  EuiText,
} from '@elastic/eui'
import { ThemeToggle } from './ThemeToggle'

export function AppHeader() {
  const navigate = useNavigate()

  return (
    <EuiHeader position="fixed">
      <EuiHeaderSection grow={false}>
        <EuiHeaderSectionItem>
          <EuiHeaderLinks>
            <EuiHeaderLink onClick={() => navigate('/atlas')}>
              <EuiText size="s" style={{ fontWeight: 600 }}>
                Atlas Memory Demo
              </EuiText>
            </EuiHeaderLink>
          </EuiHeaderLinks>
        </EuiHeaderSectionItem>
      </EuiHeaderSection>
      <EuiHeaderSection side="right">
        <EuiHeaderSectionItem>
          <ThemeToggle />
        </EuiHeaderSectionItem>
      </EuiHeaderSection>
    </EuiHeader>
  )
}
