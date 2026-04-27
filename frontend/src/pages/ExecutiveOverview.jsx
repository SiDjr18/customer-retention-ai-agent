import React, { useEffect, useState, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, ZAxis, CartesianGrid, Cell,
} from 'recharts'
import {
  Users, TrendingDown, DollarSign, AlertTriangle,
  Star, Target, RefreshCw, Zap, ShieldAlert,
} from 'lucide-react'
import KpiCard from '../components/KpiCard'
import { PageLoader, ErrorBanner } from '../components/LoadingState'
import { fetchKPIs, fetchSample, fetchPriorityList } from '../services/api'

// ── Palette ───────────────────────────────────────────────────────────────────
const REGION_COLORS = ['#3b82f6','#ef4444','#f59e0b','#22c55e','#8b5cf6','#06b6d4']
const RISK_BAND = r => r >= 0.65 ? '#ef4444' : r >= 0.4 ? '#f59e0b' : '#22c55e'
const PRIORITY_BADGE = {
  'High Priority':   'badge-high',
  'Medium Priority': 'badge-medium',
  'Low Priority':    'badge-low',
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmt$ = v => v == null ? '—' : `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
const fmtPct = v => v == null ? '—' : `${Number(v).toFixed(1)}%`

// ── Insights panel ────────────────────────────────────────────────────────────
function InsightsPanel({ kpis }) {
  const summary = kpis?.insight?.executive_summary || kpis?.executive_note
  const drivers = kpis?.insight?.key_drivers || []
  const actions = kpis?.insight?.recommended_actions || []
  if (!summary && !drivers.length) return null
  return (
    <div className="bg-slate-900 text-white rounded-xl p-5 space-y-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">AI Executive Insight</p>
      {summary && <p className="text-sm leading-relaxed text-slate-200">{summary}</p>}
      {drivers.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-400 mb-2">Key Drivers</p>
          <ul className="space-y-1">
            {drivers.slice(0, 3).map((d, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-slate-300">
                <span className="text-blue-400 mt-0.5 shrink-0">›</span>{d}
              </li>
            ))}
          </ul>
        </div>
      )}
      {actions.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-400 mb-2">Recommended Actions</p>
          <ul className="space-y-1">
            {actions.slice(0, 3).map((a, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-slate-300">
                <Zap className="w-3 h-3 text-amber-400 mt-0.5 shrink-0" />
                {typeof a === 'string' ? a : a.action ?? JSON.stringify(a)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Priority table ─────────────────────────────────────────────────────────────
function PriorityTable({ rows, loading }) {
  if (loading) return <p className="text-xs text-slate-400 py-4 text-center">Loading priority list…</p>
  if (!rows?.length) return <p className="text-xs text-slate-400 py-4 text-center">No data</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-100 text-slate-500 uppercase tracking-wide">
            <th className="text-left py-2 pr-4 font-medium">Customer</th>
            <th className="text-left py-2 pr-4 font-medium">Priority</th>
            <th className="text-right py-2 pr-4 font-medium">Est. CLV</th>
            <th className="text-right py-2 font-medium">Risk Score</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {rows.map(c => (
            <tr key={c.customer_id} className="hover:bg-slate-50 transition-colors">
              <td className="py-2 pr-4 font-medium text-slate-700">{c.customer_id}</td>
              <td className="py-2 pr-4">
                <span className={PRIORITY_BADGE[c.priority_class] || 'badge-low'}>
                  {c.priority_class?.replace(' Priority', '')}
                </span>
              </td>
              <td className="py-2 pr-4 text-right text-slate-700">{fmt$(c.estimated_clv)}</td>
              <td className="py-2 text-right font-semibold"
                  style={{ color: RISK_BAND(c.churn_risk_score) }}>
                {c.churn_risk_score?.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Export helpers ─────────────────────────────────────────────────────────────
function exportCSV(rows) {
  if (!rows?.length) return
  const cols = ['customer_id','priority_class','estimated_clv','churn_risk_score']
  const csv  = [cols.join(','), ...rows.map(r => cols.map(c => r[c] ?? '').join(','))].join('\n')
  const a    = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
    download: 'priority_customers.csv',
  })
  a.click(); URL.revokeObjectURL(a.href)
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function ExecutiveOverview() {
  const [kpis,     setKpis]     = useState(null)
  const [scatter,  setScatter]  = useState([])
  const [priority, setPriority] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [priLoading, setPriLoading] = useState(true)
  const [error,    setError]    = useState(null)

  const load = useCallback(() => {
    setLoading(true); setError(null)
    Promise.allSettled([fetchKPIs(), fetchSample(300), fetchPriorityList(10)])
      .then(([kRes, sRes, pRes]) => {
        if (kRes.status === 'fulfilled') setKpis(kRes.value)
        else setError(kRes.reason?.message || 'Failed to load KPIs')

        if (sRes.status === 'fulfilled') {
          setScatter(
            (sRes.value.records || [])
              .filter(r => r.estimated_clv != null && r.churn_risk_score != null)
              .map(r => ({ clv: Math.round(r.estimated_clv), risk: +r.churn_risk_score.toFixed(3) }))
          )
        }

        if (pRes.status === 'fulfilled') setPriority(pRes.value.customers || [])
        setPriLoading(false)
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <PageLoader label="Loading executive overview…" />
  if (error)   return <div className="p-6"><ErrorBanner message={error} /></div>
  if (!kpis)   return null

  // Support both flat (legacy) and nested (new) API shapes
  const core = kpis.core_kpis ?? kpis
  const biz  = kpis.business_metrics ?? {}

  const regionData = Object.entries(core.churn_by_region || {})
    .map(([name, value]) => ({ name, value: +value.toFixed(1) }))
    .sort((a, b) => b.value - a.value)

  const segData = Object.entries(core.churn_by_segment || {})
    .map(([name, value]) => ({ name, value: +value.toFixed(1) }))
    .sort((a, b) => b.value - a.value)

  return (
    <div className="p-6 space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <h1 className="page-title">Executive Overview</h1>
        <button onClick={load} className="btn-ghost flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* ── Core KPI cards ── */}
      <div className="grid grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6 gap-4">
        <KpiCard label="Total Customers"
          value={core.total_customers?.toLocaleString()}
          icon={<Users className="w-5 h-5" />} accent="bg-blue-500" />
        <KpiCard label="Churn Rate"
          value={fmtPct(core.churn_rate_pct)}
          sub="% of customers churned"
          icon={<TrendingDown className="w-5 h-5" />} accent="bg-red-500" />
        <KpiCard label="Avg CLV"
          value={fmt$(core.avg_clv)}
          sub="Customer Lifetime Value"
          icon={<DollarSign className="w-5 h-5" />} accent="bg-green-500" />
        <KpiCard label="Revenue at Risk"
          value={fmt$(biz.revenue_at_risk ?? core.revenue_at_risk)}
          sub={biz.revenue_at_risk ? 'Risk score > 0.6' : 'From churned accounts'}
          icon={<AlertTriangle className="w-5 h-5" />} accent="bg-amber-500" />
        <KpiCard label="High-Value Customers"
          value={biz.high_value_customers?.toLocaleString() ?? '—'}
          sub={biz.high_value_pct != null ? `${biz.high_value_pct.toFixed(1)}% of base` : 'CLV > 75th pct'}
          icon={<ShieldAlert className="w-5 h-5" />} accent="bg-purple-500" />
        <KpiCard label="Avg Risk Score"
          value={core.avg_churn_risk_score?.toFixed(2)}
          sub="0 = safe · 1 = certain churn"
          icon={<Target className="w-5 h-5" />} accent="bg-cyan-500" />
      </div>

      {/* ── Charts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Region bar */}
        {regionData.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <p className="section-title">Churn Rate by Region (%)</p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={regionData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit="%" />
                <Tooltip formatter={v => `${v}%`} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {regionData.map((_, i) => (
                    <Cell key={i} fill={REGION_COLORS[i % REGION_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Segment bar */}
        {segData.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <p className="section-title">Churn Rate by Segment (%)</p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={segData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit="%" />
                <Tooltip formatter={v => `${v}%`} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]} fill="#8b5cf6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* CLV vs Risk scatter */}
        {scatter.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <p className="section-title">CLV vs Churn Risk Score</p>
            <ResponsiveContainer width="100%" height={220}>
              <ScatterChart margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="risk" name="Risk" type="number" domain={[0,1]}
                  tick={{ fontSize: 10 }} label={{ value: 'Risk Score', position: 'insideBottom', offset: -2, fontSize: 10 }} />
                <YAxis dataKey="clv" name="CLV" tick={{ fontSize: 10 }}
                  tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                <ZAxis range={[18, 18]} />
                <Tooltip cursor={{ strokeDasharray: '3 3' }}
                  formatter={(v, n) => n === 'CLV' ? fmt$(v) : v} />
                <Scatter data={scatter} fill="#3b82f6" fillOpacity={0.5} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Insights panel */}
        <InsightsPanel kpis={kpis} />
      </div>

      {/* ── Top Priority Customers ── */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="section-title mb-0">Top Priority Customers</p>
          <button onClick={() => exportCSV(priority)}
            className="text-xs text-blue-600 hover:underline font-medium">
            Export CSV
          </button>
        </div>
        <PriorityTable rows={priority} loading={priLoading} />
      </div>
    </div>
  )
}
