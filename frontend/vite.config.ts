import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite Configuration for EUI
 * 
 * Key settings:
 * - React plugin with Emotion for EUI's CSS-in-JS
 * - Optimized dependencies for faster dev startup
 * - Dynamic port configuration to avoid conflicts
 * 
 * Port Configuration:
 * - The ./dev script auto-detects port conflicts and finds available ports
 * - It passes VITE_BACKEND_PORT to tell Vite where to proxy API requests
 * - Defaults here should match ./dev script defaults (8001 backend, 3000 frontend)
 * - When running multiple demos, ports may be incremented (8002, 8003, etc.)
 * 
 * @see ./dev script for port auto-detection logic
 */

// Read ports from environment (set by ./dev script) or use defaults
// Priority: env vars from dev script > legacy env vars > defaults matching ./dev script
const FRONTEND_PORT = parseInt(process.env.VITE_PORT || process.env.FRONTEND_PORT || '3000')
const BACKEND_PORT = parseInt(process.env.VITE_BACKEND_PORT || process.env.BACKEND_PORT || process.env.PORT || '8001')

// Base path for Cloud Run deployment (e.g., /template/, /ecommerce/)
// Defaults to '/' for local development
const BASE_PATH = process.env.VITE_BASE_PATH || '/'

export default defineConfig({
  // Base URL for assets - required for subpath deployments
  base: BASE_PATH,
  plugins: [
    react({
      jsxImportSource: '@emotion/react',
    }),
  ],
  // Pre-bundle EUI for faster dev server startup
  optimizeDeps: {
    include: [
      '@elastic/eui',
      '@elastic/eui-theme-borealis',
      '@emotion/react',
      '@emotion/cache',
      'react-router-dom',
    ],
  },
  server: {
    port: FRONTEND_PORT,
    // Proxy API requests to FastAPI backend
    proxy: {
      '/api': {
        target: `http://localhost:${BACKEND_PORT}`,
        changeOrigin: true,
      },
    },
  },
})
