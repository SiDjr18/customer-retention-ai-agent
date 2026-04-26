import React, { useEffect, useState, useCallback } from 'react'
import { Search, ChevronUp, ChevronDown } from 'lucide-react'
import FilterBar from '../components/FilterBar'
import { PageLoader, ErrorBanner, Spinner } from '../components/LoadingState'
import { filterDataset, fetchSample } from '../services/api'

function RiskBadge({ score }) {
  if (score >= 0.65) return <span className="badge-high">High</span>
  if (score >= 0.35) return <span className="badge-medium">Medium</span>
  return <span className="badge-low">Low</span>
}

const COLS = [
  { key: 'customer_id',       label: 'Customer ID' },
  { key: 'region',            label: 'Region' },
  { key: 'customer_segment',  label: 'Segment' },
  { key: 'plan_type',         label: 'Plan' },
  { key: 'churn_risk_score',  label: 'Risk Score' },
  { key: 'estimated_clv',     label: 'CLV ($)' },
  { key: 'satisfaction_score',label: 'CSAT' },
  { key: 'churn_flag',        label: 'Churned' },
]

export default function RiskExplorer() {
  const [records, setRecords] = useState([])
  const [totalMatches, setTotalMatches] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [filters, setFilters] = useState({})
  const [search, setSearch]   = useState('')
  const [sort, setSort]       = useState({ key: 'churn_risk_score', dir: 'desc' })

  const load = useCallback(async (f) => {
    setLoading(true)
    try {
      const res = await filterDataset({ ...f, limit: 200 })
      setRecords(res.records)
      setTotalMatches(res.total_matches)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(filters) }, [filters, load])

  const handleFilter = (key, val) => {
    setFilters(prev => {
      const next = { ...prev }
      if (val === null) delete next[key]
      else next[key] = val
      return next
    })
  }

  const handleSort = (key) => {
    setSort(prev =>
      prev.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'desc' }
    )
  }

  const sorted = [...records]
    .filter(r =>
      !search ||
      Object.values(r).some(v =>
        String(v).toLowerCase().includes(search.toLowerCase())
      )
    )
    .sort((a, b) => {
      const av = a[sort.key] ?? ''
      const bv = b[sort.key] ?? ''
      const cmp = av < bv ? -1 : av > bv ? 1 : 0
      return sort.dir === 'asc' ? cmp : -cmp
    })

  return (
    <div>
      <FilterBar filters={filters} onFilterChange={handleFilter} />
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="page-title">Customer Risk Explorer</h1>
          <span className="text-xs text-slate-400">{totalMatches.toLocaleString()} customers matched</span>
        </div>

        {/* Search */}
        <div className="relative max-w-xs">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>

        {error && <ErrorBanner message={error} />}

        {loading ? (
          <PageLoader label="Fetching customers…" />
        ) : (
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr>
                  {COLS.map(col => (
                    <th
                      key={col.key}
                      onClick={() => handleSort(col.key)}
                      className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide cursor-pointer hover:text-slate-800 whitespace-nowrap select-none"
                    >
                      <span className="flex items-center gap-1">
                        {col.label}
                        {sort.key === col.key
                          ? sort.dir === 'asc'
                            ? <ChevronUp className="w-3 h-3" />
                            : <ChevronDown className="w-3 h-3" />
                          : null}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {sorted.slice(0, 100).map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50 transition-colors">
                    {COLS.map(col => (
                      <td key={col.key} className="px-4 py-2.5 whitespace-nowrap text-slate-700">
                        {col.key === 'churn_risk_score' ? (
                          <div className="flex items-center gap-2">
                            <span>{row[col.key]?.toFixed ? row[col.key].toFixed(2) : row[col.key]}</span>
                            <RiskBadge score={parseFloat(row[col.key]) || 0} />
                          </div>
                        ) : col.key === 'churn_flag' ? (
                          row[col.key] == 1
                            ? <span className="badge-high">Yes</span>
                            : <span className="badge-low">No</span>
                        ) : col.key === 'estimated_clv' ? (
                          `$${parseFloat(row[col.key] || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
                        ) : (
                          row[col.key] ?? '—'
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {sorted.length === 0 && (
              <p className="text-center py-10 text-sm text-slate-400">No records match the current filters.</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
