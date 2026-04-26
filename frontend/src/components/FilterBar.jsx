import React from 'react'
import { SlidersHorizontal } from 'lucide-react'

const FILTER_FIELDS = [
  { key: 'region',             label: 'Region' },
  { key: 'customer_segment',   label: 'Segment' },
  { key: 'plan_type',          label: 'Plan' },
  { key: 'contract_type',      label: 'Contract' },
  { key: 'acquisition_channel',label: 'Channel' },
]

/**
 * Sticky top filter bar.
 * @param {object}   filters       - current filter state { region, customer_segment, … }
 * @param {function} onFilterChange - (key, value) => void
 * @param {object}   options        - { region: [], customer_segment: [], … }
 */
export default function FilterBar({ filters = {}, onFilterChange, options = {} }) {
  return (
    <div className="sticky top-0 z-10 bg-white border-b border-slate-100 px-6 py-3 flex items-center gap-4 shadow-sm">
      <SlidersHorizontal className="w-4 h-4 text-slate-400 shrink-0" />
      <span className="text-xs font-medium text-slate-500 shrink-0">Filters:</span>

      {FILTER_FIELDS.map(({ key, label }) => (
        <select
          key={key}
          value={filters[key] || ''}
          onChange={e => onFilterChange(key, e.target.value || null)}
          className="text-xs border border-slate-200 rounded-md px-2 py-1.5 bg-white text-slate-700
                     focus:outline-none focus:ring-1 focus:ring-blue-400 min-w-[110px]"
        >
          <option value="">All {label}s</option>
          {(options[key] || []).map(opt => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      ))}

      <button
        onClick={() => FILTER_FIELDS.forEach(f => onFilterChange(f.key, null))}
        className="ml-auto text-xs text-slate-400 hover:text-slate-600 transition-colors"
      >
        Clear all
      </button>
    </div>
  )
}
