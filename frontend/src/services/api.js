/**
 * API service layer — all backend calls go through this module.
 * Vite dev-server proxies /api/* → http://localhost:8000/*
 */

import axios from 'axios'

const BASE = '/api'

const client = axios.create({
  baseURL: BASE,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Health ────────────────────────────────────────────────────────────────────
export const fetchHealth = () => client.get('/health').then(r => r.data)

// ── Dataset ───────────────────────────────────────────────────────────────────
export const fetchKPIs    = ()       => client.get('/dataset/kpis').then(r => r.data)
export const fetchProfile = ()       => client.get('/dataset/profile').then(r => r.data)
export const fetchColumns = ()       => client.get('/dataset/columns').then(r => r.data)
export const fetchSample  = (n = 50) => client.get(`/dataset/sample?n=${n}`).then(r => r.data)
export const filterDataset = (body)  => client.post('/dataset/filter', body).then(r => r.data)

// ── Predictions ───────────────────────────────────────────────────────────────
export const predictChurn     = (body) => client.post('/predict/churn', body).then(r => r.data)
export const predictBatch     = (body) => client.post('/predict/batch', body).then(r => r.data)
export const fetchModelMetrics = ()    => client.get('/predict/metrics').then(r => r.data)

// ── Recommendations ───────────────────────────────────────────────────────────
export const recommendCustomer  = (body) => client.post('/recommend/customer', body).then(r => r.data)
export const recommendBatch     = (body) => client.post('/recommend/batch', body).then(r => r.data)
export const fetchStrategySummary = ()   => client.get('/recommend/strategy-summary').then(r => r.data)

// ── Agent ─────────────────────────────────────────────────────────────────────
export const agentChat = (message, context = null) =>
  client.post('/agent/chat', { message, context }).then(r => r.data)

// ── Reports ───────────────────────────────────────────────────────────────────
export const generatePdfReport = (body = {}) => client.post('/reports/pdf', body).then(r => r.data)
export const generateCsvReport = (body = {}) => client.post('/reports/csv', body).then(r => r.data)
export const generatePptReport = (body = {}) => client.post('/reports/ppt', body).then(r => r.data)
export const downloadReportUrl  = (filename) => `${BASE}/reports/export/${filename}`
