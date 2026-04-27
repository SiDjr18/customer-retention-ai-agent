import React, { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { Lightbulb, RefreshCw } from 'lucide-react'
import { PageLoader, ErrorBanner } from '../components/LoadingState'
import { fetchStrategySummary, fetchPriorityList } from '../services/api'

const STRATEGY_COLORS = {
  'Premium Retention Offer': '#ef4444',
  'Service Recovery Call':   '#f97316',
  'Payment Support Plan':    '#f59e0b',
  'Upsell Premium Plan':     '#22c55e',
  'CX Intervention':         '#3b82f6',
  'Monitor':                 '#94a3b8',
}

const PRIORITY_BADGE = {
  'High Priority':   'badge-high',
  'Medium Priority': 'badge-medium',
  'Low Priority':    'badge-low',
}

const RISK_COLOR = r => r >= 0.65 ? '#ef4444' : r >= 0.4 ? '#f59e0b' : '#22c55e'

const fmt$ = v => v == null ? '—'
  : `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`

function exportCSV(rows) {
  if (!rows?.length) return
  const cols = ['customer_id','region','customer_segment','plan_type',
                'estimated_clv','churn_risk_score','complaints_90d',
                'priority_score','priority_class','recommended_action']
  const csv = [cols.join(','),
    ...rows.map(r => cols.map(c => `"${r[c] ?? ''}"`).join(','))
  ].join('\n')
  const a = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
    download: 'priority_customers.csv',
  })
  a.click(); URL.revokeObjectURL(a.href)
}

export default function Recommendations() {
  const [summary,  setSummary]  = useState(null)
  const [priority, setPriority] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [priLoad,  setPriLoad]  = useState(true)
  const [error,    setError]    = useState(null)

  const load = () => {
    setLoading(true); setError(null)
    fetchStrategySummary()
      .then(setSummary)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))

    setPriLoad(true)
    fetchPriorityList(500)
      .then(d => setPriority(d))
      .catch(() => setPriority(null))
      .finally(() => setPriLoad(false))
  }

  useEffect(() => { load() }, [])

  if (loading) return <PageLoader label="Loading strategy summary…" />

  return (
    <div className="p-6 space-y-6">
      {/* ── Header ── */}
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
                {fmt$(summary.strategies?.reduce((s, b) => s + b.total_revenue_protected, 0))}
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
                  formatter={(v, n) =>
                    n === 'customer_count' ? `${v} customers` : fmt$(v)
                  }
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
                  Est. protected: {fmt$(b.total_revenue_protected)}
                </p>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Priority Customer List ── */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="section-title mb-0">Priority Customer Action List</p>
          {priority && (
            <div className="flex items-center gap-4">
              <span className="text-xs text-slate-400">
                {priority.high_priority_count ?? 0} High ·{' '}
                {priority.medium_priority_count ?? 0} Medium ·{' '}
                {priority.low_priority_count ?? 0} Low
              </span>
              <button
                onClick={() => exportCSV(priority?.customers)}
                className="text-xs text-blue-600 hover:underline font-medium"
              >
                Export CSV
              </button>
            </div>
          )}
        </div>

        {priLoad && (
          <p className="text-xs text-slate-400 py-6 text-center">Loading priority list…</p>
        )}

        {!priLoad && !priority && (
          <p className="text-xs text-slate-400 py-6 text-center">
            Priority list unavailable — check backend connection.
          </p>
        )}

        {!priLoad && priority?.customers?.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-slate-500 uppercase tracking-wide">
                  <th className="text-left py-2 pr-3 font-medium">Customer ID</th>
                  <th className="text-left py-2 pr-3 font-medium">Priority</th>
                  <th className="text-left py-2 pr-3 font-medium">Region</th>
                  <th className="text-left py-2 pr-3 font-medium">Segment</th>
                  <th className="text-right py-2 pr-3 font-medium">Est. CLV</th>
                  <th className="text-right py-2 pr-3 font-medium">Risk Score</th>
                  <th className="text-right py-2 pr-3 font-medium">Priority Score</th>
                  <th className="text-left py-2 font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {priority.customers.map(c => (
                  <tr key={c.customer_id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2 pr-3 font-medium text-slate-700">{c.customer_id}</td>
                    <td className="py-2 pr-3">
                      <span className={PRIORITY_BADGE[c.priority_class] || 'badge-low'}>
                        {c.priority_class?.replace(' Priority', '')}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-slate-600">{c.region}</td>
                    <td className="py-2 pr-3 text-slate-600">{c.customer_segment}</td>
                    <td className="py-2 pr-3 text-right text-slate-700">{fmt$(c.estimated_clv)}</td>
                    <td className="py-2 pr-3 text-right font-semibold"
                        style={{ color: RISK_COLOR(c.churn_risk_score) }}>
                      {c.churn_risk_score?.toFixed(3)}
                    </td>
                    <td className="py-2 pr-3 text-right text-slate-600">
                      {c.priority_score?.toFixed(3)}
                    </td>
                    <td className="py-2 text-slate-500 max-w-[180px] truncate" title={c.recommended_action}>
                      {c.recommended_action}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
