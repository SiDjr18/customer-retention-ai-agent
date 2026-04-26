import React, { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { Users, TrendingDown, DollarSign, AlertTriangle, Star, Target } from 'lucide-react'
import KpiCard from '../components/KpiCard'
import { PageLoader, ErrorBanner } from '../components/LoadingState'
import { fetchKPIs } from '../services/api'

const PIE_COLORS = ['#3b82f6', '#ef4444', '#f59e0b', '#22c55e', '#8b5cf6', '#06b6d4']

export default function ExecutiveOverview() {
  const [kpis, setKpis] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchKPIs()
      .then(setKpis)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <PageLoader label="Loading executive overview…" />
  if (error)   return <div className="p-6"><ErrorBanner message={error} /></div>
  if (!kpis)   return null

  const regionData = Object.entries(kpis.churn_by_region || {})
    .map(([name, value]) => ({ name, value: parseFloat(value.toFixed(1)) }))
    .sort((a, b) => b.value - a.value)

  const segmentData = Object.entries(kpis.churn_by_segment || {})
    .map(([name, value]) => ({ name, value: parseFloat(value.toFixed(1)) }))

  return (
    <div className="p-6 space-y-6">
      <h1 className="page-title">Executive Overview</h1>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6 gap-4">
        <KpiCard
          label="Total Customers"
          value={kpis.total_customers?.toLocaleString()}
          icon={<Users className="w-5 h-5" />}
          accent="bg-blue-500"
        />
        <KpiCard
          label="Churn Rate"
          value={`${kpis.churn_rate_pct?.toFixed(1)}%`}
          sub="% of customers churned"
          icon={<TrendingDown className="w-5 h-5" />}
          accent="bg-red-500"
        />
        <KpiCard
          label="Avg CLV"
          value={`$${kpis.avg_clv?.toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
          sub="Customer Lifetime Value"
          icon={<DollarSign className="w-5 h-5" />}
          accent="bg-green-500"
        />
        <KpiCard
          label="Revenue at Risk"
          value={`$${kpis.revenue_at_risk?.toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
          sub="From churned customers"
          icon={<AlertTriangle className="w-5 h-5" />}
          accent="bg-amber-500"
        />
        <KpiCard
          label="Avg Risk Score"
          value={kpis.avg_churn_risk_score?.toFixed(2)}
          sub="0 = no risk, 1 = certain churn"
          icon={<Target className="w-5 h-5" />}
          accent="bg-purple-500"
        />
        <KpiCard
          label="Avg Satisfaction"
          value={kpis.avg_satisfaction_score?.toFixed(1)}
          sub="Scale 0–10"
          icon={<Star className="w-5 h-5" />}
          accent="bg-cyan-500"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bar — churn by region */}
        {regionData.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <p className="section-title">Churn Rate by Region (%)</p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={regionData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit="%" />
                <Tooltip formatter={v => `${v}%`} />
                <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Pie — churn by segment */}
        {segmentData.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <p className="section-title">Churn Distribution by Segment (%)</p>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={segmentData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label={({ name, value }) => `${name}: ${value}%`}
                  labelLine={false}
                >
                  {segmentData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Tooltip formatter={v => `${v}%`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
