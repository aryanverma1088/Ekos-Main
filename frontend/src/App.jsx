import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import KnowledgeGraph from './pages/KnowledgeGraph'
import IntegrityCenter from './pages/IntegrityCenter'
import Documents from './pages/Documents'
import DocumentDetail from './pages/DocumentDetail'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="search" element={<Search />} />
          <Route path="graph" element={<KnowledgeGraph />} />
          <Route path="integrity" element={<IntegrityCenter />} />
          <Route path="documents" element={<Documents />} />
          <Route path="documents/:id" element={<DocumentDetail />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
