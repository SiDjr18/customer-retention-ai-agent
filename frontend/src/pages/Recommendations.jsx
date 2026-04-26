import React, { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { Lightbulb, RefreshCw } from 'lucide-react'
import { PageLoader, ErrorBanner } from '../components/LoadingState'
import { fetchStrategySummary } from '../services/api'

const STRATEGY_COLORS = {
  'Premium Retention Offer': '#ef4444',
  'Service Recovery Call':   '#f97316',
  'Payment Support Plan':    '#f59e0b',
  'Upsell Premium Plan':     '#22c55e',
  'CX Intervention':         '#3b82f6',
  'Monitor':                 '#94a3b8',
}

const PRIORITY_COLOR = {
  Critical: 'badge-high',
  High:     'badge-high',
  Medium:   'badge-medium',
  Low:      'badge-low',
}

export default function Recommendations() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchStrategySummary()
      .then(setSummary)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  if (loading) return <PageLoader label="Loading strategy summary…" />

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="page-title">Retention Recommendations</h1>
        <button onClick={load} className="btn-ghost flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {error && <ErrorBanner message={error} />}

      {summary && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-2 gap-4">
            <div className="kpi-card">
              <p className="kpi-label">Customers Analysed</p>
              <p className="kpi-value">{summary.total_customers_analysed?.toLocaleString()}</p>
            </div>
            <div className="kpi-card">
              <p className="kpi-label">Total Revenue Protected (Est.)</p>
              <p className="kpi-value text-green-600">
                ${summary.strategies?.reduce((s, b) => s + b.total_revenue_protected, 0)
                    .toLocaleString('en-US', { maximumFractionDigits: 0 })}
              </p>
            </div>
          </div>

          {/* Bar chart */}
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <p className="section-title">Strategy Distribution</p>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={summary.strategies}
                margin={{ top: 4, right: 8, bottom: 40, left: 0 }}
              >
                <XAxis dataKey="strategy" tick={{ fontSize: 10 }} angle={-15} textAnchor="end" />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip
                  formatter={(v, n) => n === 'customer_count' ? `${v} customers` : `$${v.toLocaleString()}`}
                />
                <Bar dataKey="customer_count" radius={[4, 4, 0, 0]}>
                  {summary.strategies.map((s, i) => (
                    <Cell key={i} fill={STRATEGY_COLORS[s.strategy] || '#94a3b8'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Strategy cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {summary.strategies.map(b => (
              <div key={b.strategy} className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
                <div className="flex items-start justify-between mb-2">
                  <p className="text-sm font-semibold text-slate-800">{b.strategy}</p>
                  <Lightbulb
                    className="w-4 h-4 shrink-0"
                    style={{ color: STRATEGY_COLORS[b.strategy] || '#94a3b8' }}
                  />
                </div>
                <p className="text-2xl font-bold text-slate-800">{b.customer_count.toLocaleString()}</p>
                <p className="text-xs text-slate-400 mt-0.5">{b.pct_of_total.toFixed(1)}% of total</p>
                <p className="text-xs text-green-600 font-medium mt-2">
                  Est. protected: ${b.total_revenue_protected.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                </p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
