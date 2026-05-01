import React, { useEffect, useState } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip,
} from 'recharts'
import { Brain, RefreshCw } from 'lucide-react'
import { PageLoader, ErrorBanner, Spinner } from '../components/LoadingState'
import { fetchModelMetrics } from '../services/api'

function MetricBadge({ label, value }) {
  return (
    <div className="bg-slate-50 rounded-lg p-3 text-center">
      <p className="text-xs text-slate-500 uppercase tracking-wide">{label}</p>
      <p className="text-xl font-bold text-slate-800 mt-0.5">
        {typeof value === 'number' ? (value * 100).toFixed(1) + '%' : '—'}
      </p>
    </div>
  )
}

export default function ChurnPrediction() {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchModelMetrics()
      .then(setMetrics)
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  if (loading) return <PageLoader label="Loading model metrics…" />

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="page-title">Churn Prediction Model</h1>
        <button onClick={load} className="btn-ghost flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {error && (
        <div className="space-y-2">
          <ErrorBanner message={error} />
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
            <strong>To train the model:</strong>
            <pre className="mt-2 bg-amber-100 rounded p-2 text-xs overflow-auto">
              cd backend{'\n'}
              python -m app.services.model_training
            </pre>
          </div>
        </div>
      )}

      {metrics && (
        <>
          {/* Best model banner */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center gap-3">
            <Brain className="w-6 h-6 text-blue-600 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-blue-800">
                Best Model: {metrics.best_model}
              </p>
              <p className="text-xs text-blue-600">
                Trained on {metrics.training_samples?.toLocaleString()} samples · {metrics.trained_at?.slice(0, 10)}
              </p>
            </div>
          </div>

          {/* Metrics comparison */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {(metrics.metrics || []).map(m => (
              <div key={m.model_name} className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
                <p className="section-title">{m.model_name}</p>
                <div className="grid grid-cols-3 gap-2 mb-4">
                  <MetricBadge label="Accuracy"  value={m.accuracy}  />
                  <MetricBadge label="Precision" value={m.precision} />
                  <MetricBadge label="Recall"    value={m.recall}    />
                  <MetricBadge label="F1 Score"  value={m.f1_score}  />
                  <MetricBadge label="ROC-AUC"   value={m.roc_auc}   />
                </div>
              </div>
            ))}
          </div>

          {/* Feature importance */}
          {metrics.feature_importance?.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
              <p className="section-title">Top Feature Importances</p>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={metrics.feature_importance.slice(0, 15)}
                  layout="vertical"
                  margin={{ top: 0, right: 20, bottom: 0, left: 140 }}
                >
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis dataKey="feature" type="category" tick={{ fontSize: 10 }} width={140} />
                  <Tooltip formatter={v => v.toFixed(4)} />
                  <Bar dataKey="importance" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  )
}
