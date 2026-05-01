import React, { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Lightbulb, TrendingUp, CheckCircle } from 'lucide-react'
import { Spinner } from '../components/LoadingState'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const multiAgentChat = (message, context = null) =>
  axios.post(`${API}/agent/multi-chat`, { message, context }).then(r => r.data)

const SUGGESTIONS = [
  'What is the churn rate?',
  'Give me an executive summary',
  'Which region has the highest churn?',
  'Recommend retention strategies for premium customers',
  'Simulate a $500,000 retention campaign with 10% discount',
  'Who are the top priority customers for outreach?',
  'What is the revenue at risk?',
  'What did I upload?',
]

const PRIORITY_COLORS = {
  High:   'bg-red-50 border-red-200 text-red-700',
  Medium: 'bg-amber-50 border-amber-200 text-amber-700',
  Low:    'bg-green-50 border-green-200 text-green-700',
}

function AgentResponse({ data }) {
  if (typeof data === 'string') return <p className="text-sm">{data}</p>

  const actions  = data.recommended_actions || []
  const insights = data.key_insights || data.key_findings || []
  const impact   = data.business_impact

  return (
    <div className="space-y-4">
      {/* Agent badge */}
      {data.agent_used && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
            {data.agent_used.replace(/Agent$/, ' Agent')}
          </span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium
            ${data.confidence_level === 'High'   ? 'bg-green-100 text-green-700' :
              data.confidence_level === 'Medium' ? 'bg-amber-100 text-amber-700' :
              'bg-slate-100 text-slate-600'}`}>
            {data.confidence_level} confidence
          </span>
        </div>
      )}

      {/* Executive summary */}
      {data.executive_summary && (
        <p className="text-sm text-slate-800 leading-relaxed">{data.executive_summary}</p>
      )}

      {/* Business impact */}
      {impact && (
        <div className={`rounded-lg border px-3 py-2.5 flex flex-wrap gap-4 text-xs
          ${impact.risk_level === 'Critical' || impact.risk_level === 'High'
            ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'}`}>
          {impact.revenue_at_risk && (
            <div>
              <p className="text-slate-500 uppercase tracking-wide text-[10px]">Revenue at Risk</p>
              <p className="font-bold text-slate-800 text-sm">{impact.revenue_at_risk}</p>
            </div>
          )}
          {impact.affected_customers != null && (
            <div>
              <p className="text-slate-500 uppercase tracking-wide text-[10px]">Affected Customers</p>
              <p className="font-bold text-slate-800 text-sm">{impact.affected_customers?.toLocaleString()}</p>
            </div>
          )}
          <div>
            <p className="text-slate-500 uppercase tracking-wide text-[10px]">Risk Level</p>
            <p className="font-bold text-slate-800 text-sm">{impact.risk_level}</p>
          </div>
        </div>
      )}

      {/* Key insights */}
      {insights.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Key Insights</p>
          <ul className="space-y-1">
            {insights.map((f, i) => (
              <li key={i} className="text-xs text-slate-700 flex gap-2">
                <TrendingUp className="w-3 h-3 text-blue-400 mt-0.5 shrink-0" />
                {f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommended actions */}
      {actions.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Recommended Actions</p>
          <div className="space-y-1.5">
            {actions.map((a, i) => {
              const text      = typeof a === 'string' ? a : a.action
              const rationale = typeof a === 'object' ? a.rationale : null
              const priority  = typeof a === 'object' ? (a.priority || 'Medium') : 'Medium'
              return (
                <div key={i} className={`rounded-lg border px-2.5 py-2 ${PRIORITY_COLORS[priority] || PRIORITY_COLORS.Medium}`}>
                  <div className="flex items-start gap-1.5">
                    <CheckCircle className="w-3 h-3 mt-0.5 shrink-0" />
                    <div className="flex-1">
                      <p className="text-xs font-medium">{text}</p>
                      {rationale && <p className="text-[11px] opacity-75 mt-0.5">{rationale}</p>}
                    </div>
                    <span className="ml-2 text-[10px] font-bold shrink-0">{priority}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5
        ${isUser ? 'bg-blue-600' : 'bg-slate-700'}`}>
        {isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
      </div>
      <div className={`max-w-[82%] rounded-xl px-4 py-3 text-sm leading-relaxed
        ${isUser ? 'bg-blue-600 text-white' : 'bg-white border border-slate-100 text-slate-800 shadow-sm'}`}>
        {isUser ? <p>{msg.content}</p> : <AgentResponse data={msg.content} />}
      </div>
    </div>
  )
}

export default function AgentChat() {
  const [messages, setMessages] = useState([{
    role: 'agent',
    content: {
      agent_used: 'CustomerRetentionAgent',
      confidence_level: 'High',
      executive_summary: "Hi! I'm your Customer Retention AI Agent. I route your questions to specialist analysts — data, strategy, scenario planning, and executive briefing. Ask me anything below.",
      key_insights: [],
      recommended_actions: [],
    },
  }])
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef             = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async (text) => {
    const msg = (text || input).trim()
    if (!msg || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setLoading(true)
    try {
      const res = await multiAgentChat(msg)
      setMessages(prev => [...prev, { role: 'agent', content: res }])
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'agent',
        content: {
          agent_used: 'ErrorHandler',
          confidence_level: 'Low',
          executive_summary: `Error: ${e.response?.data?.detail || e.message}. Make sure the backend is running at ${API}.`,
          key_insights: [],
          recommended_actions: [],
        },
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-48px)]">
      <div className="px-6 py-4 border-b border-slate-100 bg-white shrink-0">
        <h1 className="page-title">AI Agent Chat</h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Multi-agent orchestrator — routes to specialist analysts automatically · No paid API required
        </p>
      </div>

      <div className="px-6 py-2.5 bg-slate-50 border-b border-slate-100 flex gap-2 flex-wrap shrink-0">
        <Lightbulb className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
        {SUGGESTIONS.map(s => (
          <button key={s} onClick={() => send(s)}
            className="text-xs bg-white border border-slate-200 rounded-full px-3 py-1 text-slate-600
                       hover:border-blue-300 hover:text-blue-600 transition-colors">
            {s}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}
        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-white border border-slate-100 rounded-xl px-4 py-3 shadow-sm flex items-center gap-2">
              <Spinner size="sm" />
              <span className="text-xs text-slate-400">Analysing…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="px-6 py-4 border-t border-slate-100 bg-white shrink-0">
        <div className="flex gap-3">
          <input type="text" value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder="Ask about churn, revenue risk, strategies, scenarios…"
            className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm
                       focus:outline-none focus:ring-1 focus:ring-blue-400" />
          <button onClick={() => send()} disabled={loading || !input.trim()}
            className="btn-primary flex items-center gap-2 disabled:opacity-40">
            <Send className="w-4 h-4" /> Send
          </button>
        </div>
      </div>
    </div>
  )
}
