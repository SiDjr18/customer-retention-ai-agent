import React, { useState } from 'react'
import { FileDown, FileText, FileSpreadsheet, Presentation, CheckCircle, AlertCircle } from 'lucide-react'
import { Spinner } from '../components/LoadingState'
import { generatePdfReport, generateCsvReport, generatePptReport, downloadReportUrl } from '../services/api'

function ReportCard({ icon: Icon, title, description, format, onGenerate, loading, result, error }) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5 flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <div className="p-2 bg-slate-50 rounded-lg">
          <Icon className="w-5 h-5 text-slate-600" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-800">{title}</p>
          <p className="text-xs text-slate-400 mt-0.5">{description}</p>
        </div>
      </div>

      {result && (
        <div className="flex items-center gap-2 bg-green-50 rounded-lg p-3">
          <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-green-700 truncate">{result.filename}</p>
            <p className="text-xs text-green-600">
              {result.size_bytes ? `${(result.size_bytes / 1024).toFixed(1)} KB` : ''} · {result.generated_at?.slice(0, 10)}
            </p>
          </div>
          <a
            href={downloadReportUrl(result.filename)}
            download={result.filename}
            className="text-xs font-medium text-green-700 hover:text-green-900 underline shrink-0"
          >
            Download
          </a>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 bg-red-50 rounded-lg p-3">
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
          <p className="text-xs text-red-700">{error}</p>
        </div>
      )}

      <button
        onClick={onGenerate}
        disabled={loading}
        className="btn-primary flex items-center justify-center gap-2 w-full disabled:opacity-50"
      >
        {loading ? <Spinner size="sm" /> : <FileDown className="w-4 h-4" />}
        {loading ? 'Generating…' : `Generate ${format}`}
      </button>
    </div>
  )
}

export default function Reports() {
  const [state, setState] = useState({ pdf: {}, csv: {}, ppt: {} })

  const handle = (key, fn) => async () => {
    setState(prev => ({ ...prev, [key]: { loading: true, result: null, error: null } }))
    try {
      const res = await fn({})
      setState(prev => ({ ...prev, [key]: { loading: false, result: res } }))
    } catch (e) {
      setState(prev => ({
        ...prev,
        [key]: { loading: false, error: e.response?.data?.detail || e.message },
      }))
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="page-title">Reports</h1>
      <p className="text-sm text-slate-500">
        Generate downloadable reports from the current dataset and model outputs.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ReportCard
          icon={FileText}
          title="PDF Executive Report"
          description="KPI snapshot, churn drivers, regional breakdown, and recommendations."
          format="PDF"
          loading={state.pdf.loading}
          result={state.pdf.result}
          error={state.pdf.error}
          onGenerate={handle('pdf', generatePdfReport)}
        />
        <ReportCard
          icon={FileSpreadsheet}
          title="CSV Customer Action List"
          description="High-risk customers enriched with NBA recommendations."
          format="CSV"
          loading={state.csv.loading}
          result={state.csv.result}
          error={state.csv.error}
          onGenerate={handle('csv', generateCsvReport)}
        />
        <ReportCard
          icon={Presentation}
          title="PPT Business Summary"
          description="PowerPoint deck (or Markdown fallback) for leadership review."
          format="PPT"
          loading={state.ppt.loading}
          result={state.ppt.result}
          error={state.ppt.error}
          onGenerate={handle('ppt', generatePptReport)}
        />
      </div>
    </div>
  )
}
