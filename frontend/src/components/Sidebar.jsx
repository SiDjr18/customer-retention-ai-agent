import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Users, Brain, Lightbulb,
  MessageSquare, FileDown, Activity,
} from 'lucide-react'

const NAV = [
  { to: '/',             icon: LayoutDashboard, label: 'Executive Overview' },
  { to: '/risk',         icon: Users,           label: 'Risk Explorer' },
  { to: '/predict',      icon: Brain,           label: 'Churn Prediction' },
  { to: '/recommend',    icon: Lightbulb,       label: 'Recommendations' },
  { to: '/agent',        icon: MessageSquare,   label: 'AI Agent' },
  { to: '/reports',      icon: FileDown,        label: 'Reports' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 min-h-screen bg-slate-900 text-white flex flex-col shrink-0">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-400" />
          <span className="text-sm font-semibold leading-tight">
            Retention<br />
            <span className="text-blue-400 font-bold">AI Agent</span>
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-2 space-y-0.5">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ` +
              (isActive
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-800')
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-slate-700 text-xs text-slate-500">
        v0.1.0 · AI Decision Intelligence
      </div>
    </aside>
  )
}
