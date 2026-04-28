import React, { useRef, useState } from 'react'
import { Upload, X, CheckCircle, AlertTriangle, Loader } from 'lucide-react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const ACCEPTED = '.csv,.xlsx,.xls,.txt,.pdf'

export default function UploadButton() {
  const inputRef                      = useRef(null)
  const [status, setStatus]           = useState('idle') // idle | uploading | done | error
  const [result, setResult]           = useState(null)
  const [error, setError]             = useState('')
  const [panelOpen, setPanelOpen]     = useState(false)

  async function handleFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''          // allow re-upload of the same file

    setStatus('uploading')
    setError('')
    setResult(null)
    setPanelOpen(true)

    const fd = new FormData()
    fd.append('file', file)

    try {
      const res = await fetch(`${API}/upload/data`, { method: 'POST', body: fd })
      if (!res.ok) {
        const msg = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(msg.detail || 'Upload failed')
      }
      const data = await res.json()
      setResult(data)
      setStatus('done')
    } catch (err) {
      setError(err.message || 'Upload failed')
      setStatus('error')
    }
  }

  function dismiss() {
    setPanelOpen(false)
    setStatus('idle')
    setResult(null)
    setError('')
  }

  return (
    <div className="relative">
      {/* Trigger button */}
      <button
        onClick={() => inputRef.current?.click()}
        disabled={status === 'uploading'}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg
                   bg-blue-600 hover:bg-blue-700 text-white transition-colors
                   disabled:opacity-60 disabled:cursor-not-allowed shadow-sm"
      >
        {status === 'uploading'
          ? <Loader className="w-3.5 h-3.5 animate-spin" />
          : <Upload className="w-3.5 h-3.5" />
        }
        {status === 'uploading' ? 'Uploading…' : 'Upload Data'}
      </button>

      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        onChange={handleFile}
        className="hidden"
      />

      {/* Result panel */}
      {panelOpen && (
        <div className="absolute right-0 top-9 z-50 w-80 bg-white border border-slate-200
                        rounded-xl shadow-xl p-4 text-sm">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <span className="font-semibold text-slate-700 text-xs uppercase tracking-wide">
              Upload Result
            </span>
            <button onClick={dismiss} className="text-slate-400 hover:text-slate-600">
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Uploading */}
          {status === 'uploading' && (
            <div className="flex items-center gap-2 text-slate-500">
              <Loader className="w-4 h-4 animate-spin text-blue-500" />
              <span>Analysing file…</span>
            </div>
          )}

          {/* Error */}
          {status === 'error' && (
            <div className="flex items-start gap-2 text-red-600">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Success */}
          {status === 'done' && result && (
            <div className="space-y-3">
              {/* Filename + type */}
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />
                <span className="font-medium text-slate-800 truncate">{result.filename}</span>
                <span className="ml-auto shrink-0 px-1.5 py-0.5 bg-slate-100 text-slate-500
                                 rounded text-xs uppercase">{result.file_type}</span>
              </div>

              {/* Domain badge */}
              <div className="flex items-center gap-2">
                <span className="text-slate-500 text-xs">Detected domain:</span>
                <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs font-medium">
                  {result.inference?.detected_domain || '—'}
                </span>
              </div>

              {/* Rows / columns */}
              {result.rows > 0 && (
                <div className="grid grid-cols-2 gap-2">
                  <Stat label="Rows" value={result.rows.toLocaleString()} />
                  <Stat label="Columns" value={result.columns?.length ?? 0} />
                </div>
              )}

              {/* Executive summary */}
              {result.inference?.executive_summary && (
                <p className="text-xs text-slate-600 leading-relaxed border-t border-slate-100 pt-2">
                  {result.inference.executive_summary.replace(/\*\*/g, '')}
                </p>
              )}

              {/* Warnings */}
              {result.warnings?.length > 0 && (
                <div className="border-t border-slate-100 pt-2 space-y-1">
                  {result.warnings.map((w, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-amber-700 text-xs">
                      <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Hint */}
              <p className="text-xs text-slate-400 border-t border-slate-100 pt-2">
                Ask the AI Agent: <em>"What is this data about?"</em>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="bg-slate-50 rounded-lg px-3 py-2 text-center">
      <div className="text-base font-semibold text-slate-800">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  )
}
