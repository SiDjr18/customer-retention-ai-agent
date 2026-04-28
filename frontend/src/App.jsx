import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import UploadButton from './components/UploadButton'
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
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        {/* Slim top bar with upload button */}
        <div className="flex items-center justify-end px-4 py-2 bg-white border-b border-slate-100 shrink-0">
          <UploadButton />
        </div>
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
    </div>
  )
}
