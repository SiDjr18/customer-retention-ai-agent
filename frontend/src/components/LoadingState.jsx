import React from 'react'

export function Spinner({ size = 'md' }) {
  const cls = size === 'sm' ? 'w-4 h-4' : size === 'lg' ? 'w-10 h-10' : 'w-6 h-6'
  return (
    <div
      className={`${cls} border-2 border-slate-200 border-t-blue-500 rounded-full animate-spin`}
      role="status"
      aria-label="Loading"
    />
  )
}

export function PageLoader({ label = 'Loading…' }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-3 text-slate-400">
      <Spinner size="lg" />
      <p className="text-sm">{label}</p>
    </div>
  )
}

export function ErrorBanner({ message }) {
  return (
    <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
      <strong>Error:</strong> {message || 'Something went wrong. Is the backend running?'}
    </div>
  )
}
