import { Outlet } from 'react-router-dom'
import { AppHeader } from './AppHeader'

/**
 * Root layout wrapper that guarantees AppHeader renders on every page.
 *
 * Pages are rendered via React Router's <Outlet /> — they no longer need
 * to import or render AppHeader themselves. Any route that genuinely needs
 * no header (e.g. an embedded overlay widget) can be placed outside the
 * <Route element={<Layout />}> group in App.tsx.
 */
export function Layout() {
  return (
    <>
      <AppHeader />
      <Outlet />
    </>
  )
}
