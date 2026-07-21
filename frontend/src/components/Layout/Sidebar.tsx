import { NavLink, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Search, BarChart3, Globe, FlaskConical,
  Swords, Lightbulb, Building2, Dna, Wifi, Cpu,
} from 'lucide-react'
import { clsx } from 'clsx'

const NAV = [
  { to: '/',            icon: Search,      label: 'Discovery',   sub: 'Studio' },
  { to: '/landscape',   icon: BarChart3,   label: 'Historical',  sub: 'Trends & Analytics' },
  { to: '/competition', icon: Swords,      label: 'Competition', sub: 'Competitive Intelligence' },
  { to: '/research',    icon: Lightbulb,   label: 'Research',    sub: 'Insights & Forecast' },
  { to: '/geo',         icon: Globe,       label: 'Geo',         sub: 'Intelligence' },
  { to: '/sites',       icon: Building2,   label: 'Sites',       sub: 'Site & Investigator' },
  { to: '/protocol',    icon: FlaskConical,label: 'Protocol',    sub: 'Analyzer' },
]

export function Sidebar() {
  const loc = useLocation()

  return (
    <aside className="w-56 flex-shrink-0 flex flex-col h-screen sticky top-0 border-r border-iq-border bg-white">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-iq-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-iq-navy flex items-center justify-center shadow-sm">
            <Dna className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="font-bold text-iq-navy text-sm leading-none">TrialLens</div>
            <div className="text-[10px] text-iq-muted mt-0.5 leading-none">Clinical Intelligence</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {NAV.map(({ to, icon: Icon, label, sub }) => {
          const active = to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(to)
          return (
            <NavLink key={to} to={to}>
              <motion.div
                whileHover={{ x: 2 }}
                whileTap={{ scale: 0.97 }}
                className={clsx(
                  'relative flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all group',
                  active
                    ? 'bg-iq-blue/10 text-iq-navy'
                    : 'text-iq-muted hover:text-iq-navy hover:bg-iq-bg',
                )}
              >
                {active && (
                  <motion.div
                    layoutId="sidebar-indicator"
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-iq-blue rounded-r-full"
                  />
                )}
                <Icon className={clsx('w-4 h-4 flex-shrink-0', active ? 'text-iq-blue' : 'group-hover:text-iq-navy')} />
                <div className="min-w-0">
                  <div className={clsx('text-sm font-semibold leading-none', active ? 'text-iq-navy' : '')}>{label}</div>
                  <div className="text-[10px] text-iq-muted mt-0.5 leading-none">{sub}</div>
                </div>
              </motion.div>
            </NavLink>
          )
        })}
      </nav>

      {/* Footer — system status */}
      <div className="px-4 py-4 border-t border-iq-border space-y-2">
        <div className="bg-iq-bg border border-iq-border rounded-lg px-3 py-2.5 flex items-center gap-2">
          <div className="relative">
            <Wifi className="w-3.5 h-3.5 text-iq-green" />
            <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-iq-green animate-pulse" />
          </div>
          <div className="min-w-0">
            <div className="text-[10px] font-semibold text-iq-green leading-none">Live Data</div>
            <div className="text-[9px] text-iq-muted mt-0.5 truncate leading-none">ClinicalTrials.gov v2</div>
          </div>
        </div>
        <div className="bg-iq-bg border border-iq-border rounded-lg px-3 py-2.5 flex items-center gap-2">
          <div className="relative">
            <Cpu className="w-3.5 h-3.5 text-iq-blue" />
            <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-iq-blue animate-pulse" />
          </div>
          <div className="min-w-0">
            <div className="text-[10px] font-semibold text-iq-blue leading-none">NLP Engine</div>
            <div className="text-[9px] text-iq-muted mt-0.5 truncate leading-none">TF-IDF · Rule-based active</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
