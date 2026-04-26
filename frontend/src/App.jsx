import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import ExecutiveOverview from './pages/ExecutiveOverview'
import RiskExplorer from './pages/RiskExplorer'
import ChurnPrediction from './pages/ChurnPrediction'
import Recommendations from './pages/Recommendations'
import AgentChat from './pages/AgentChat'
import Reports from './pages/Reports'

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/"          element={<ExecutiveOverview />} />
          <Route path="/risk"      element={<RiskExplorer />} />
          <Route path="/predict"   element={<ChurnPrediction />} />
          <Route path="/recommend" element={<Recommendations />} />
          <Route path="/agent"     element={<AgentChat />} />
          <Route path="/reports"   element={<Reports />} />
        </Routes>
      </main>
    </div>
  )
}
