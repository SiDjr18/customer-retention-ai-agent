import React from 'react'

/**
 * KpiCard — single metric tile.
 * @param {string}  label    - metric name
 * @param {string}  value    - formatted value
 * @param {string}  [sub]    - secondary info
 * @param {string}  [trend]  - "up" | "down" | "neutral"
 * @param {React.ReactNode} [icon]
 * @param {string}  [accent] - tailwind bg class for left border accent
 */
export default function KpiCard({ label, value, sub, icon, accent = 'bg-blue-500' }) {
  return (
    <div className="kpi-card relative overflow-hidden">
      {/* Accent bar */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${accent} rounded-l-xl`} />
      <div className="pl-3 flex items-start justify-between">
        <div>
          <p className="kpi-label">{label}</p>
          <p className="kpi-value">{value ?? '—'}</p>
          {sub && <p className="kpi-sub">{sub}</p>}
        </div>
        {icon && (
          <div className="p-2 bg-slate-50 rounded-lg text-slate-400">{icon}</div>
        )}
      </div>
    </div>
  )
}
