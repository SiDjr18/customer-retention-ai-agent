import React, { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Lightbulb } from 'lucide-react'
import { Spinner } from '../components/LoadingState'
import { agentChat } from '../services/api'

const SUGGESTIONS = [
  'What is the churn rate?',
  'Show top high-risk customers in the South region.',
  'Which region has the highest revenue at risk?',
  'Recommend a retention strategy for premium customers.',
  'Summarise data quality and missing values.',
  'Give me a full KPI summary.',
]

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5
        ${isUser ? 'bg-blue-600' : 'bg-slate-700'}`}>
        {isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
      </div>
      <div className={`max-w-[80%] rounded-xl px-4 py-3 text-sm leading-relaxed
        ${isUser ? 'bg-blue-600 text-white' : 'bg-white border border-slate-100 text-slate-800 shadow-sm'}`}>
        {isUser ? (
          <p>{msg.content}</p>
        ) : (
          <AgentResponse data={msg.content} />
        )}
      </div>
    </div>
  )
}

function AgentResponse({ data }) {
  if (typeof data === 'string') return <p>{data}</p>
  return (
    <div className="space-y-3">
      {data.executive_summary && (
        <p>{data.executive_summary}</p>
      )}
      {data.key_findings?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Key Findings</p>
          <ul className="space-y-0.5">
            {data.key_findings.map((f, i) => (
              <li key={i} className="text-xs text-slate-600 flex gap-1.5">
                <span className="text-blue-400 mt-0.5">•</span>{f}
              </li>
            ))}
          </ul>
        </div>
      )}
      {data.recommended_actions?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Recommended Actions</p>
          <ol className="space-y-0.5 list-decimal list-inside">
            {data.recommended_actions.map((a, i) => (
              <li key={i} className="text-xs text-slate-600">{a}</li>
            ))}
          </ol>
        </div>
      )}
      {data.confidence_level !== undefined && (
        <p className="text-xs text-slate-400">
          Confidence: {(data.confidence_level * 100).toFixed(0)}% · Intent: {data.intent}
        </p>
      )}
    </div>
  )
}

export default function AgentChat() {
  const [messages, setMessages] = useState([
    {
      role: 'agent',
      content: {
        executive_summary:
          'Hi! I\'m the Customer Retention AI Agent. Ask me anything about churn, revenue risk, customer segments, or retention strategies.',
        key_findings: [],
        recommended_actions: [],
        confidence_level: 1.0,
        intent: 'greeting',
      },
    },
  ])
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef             = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (text) => {
    const msg = text || input.trim()
    if (!msg || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setLoading(true)
    try {
      const res = await agentChat(msg)
      setMessages(prev => [...prev, { role: 'agent', content: res }])
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'agent',
        content: {
          executive_summary: `Error: ${e.response?.data?.detail || e.message}. Is the backend running?`,
          key_findings: [],
          recommended_actions: [],
          confidence_level: 0,
          intent: 'error',
        },
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-0px)]">
      <div className="px-6 py-4 border-b border-slate-100 bg-white">
        <h1 className="page-title">AI Agent Chat</h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Ask natural-language questions — no API key required
        </p>
      </div>

      {/* Suggestions */}
      <div className="px-6 py-3 bg-slate-50 border-b border-slate-100 flex gap-2 flex-wrap">
        <Lightbulb className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
        {SUGGESTIONS.map(s => (
          <button
            key={s}
            onClick={() => send(s)}
            className="text-xs bg-white border border-slate-200 rounded-full px-3 py-1 text-slate-600
                       hover:border-blue-300 hover:text-blue-600 transition-colors"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}
        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-white border border-slate-100 rounded-xl px-4 py-3 shadow-sm">
              <Spinner size="sm" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-slate-100 bg-white">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder="Ask about churn, revenue risk, strategies…"
            className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm
                       focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <button
            onClick={() => send()}
            disabled={loading || !input.trim()}
            className="btn-primary flex items-center gap-2 disabled:opacity-40"
          >
            <Send className="w-4 h-4" />
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
