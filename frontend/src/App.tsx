import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { AtlasMemoryPage } from './atlas/AtlasMemoryPage'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/atlas" element={<AtlasMemoryPage />} />
        <Route path="*" element={<Navigate to="/atlas" replace />} />
      </Route>
    </Routes>
  )
}

export default App
