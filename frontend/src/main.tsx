// Pre-register EUI icons for Vite (must be first import)
import './iconCache'

import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { BrandedThemeProvider } from './components/providers/BrandedThemeProvider'
import App from './App'

// NOTE: React.StrictMode is disabled for EUI compatibility.
// StrictMode's double-rendering corrupts EUI Emotion-based accordion animations.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <BrowserRouter basename={import.meta.env.BASE_URL}>
    <BrandedThemeProvider>
      <App />
    </BrandedThemeProvider>
  </BrowserRouter>
)
