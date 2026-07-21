import { useState, useRef, useEffect } from 'react'
import { Bell, HelpCircle, User, Sparkles, ChevronRight, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useSharedSearch, filterParams } from '@/context/SearchContext'
import { Badge } from '@/components/common/Badge'
import { api } from '@/api/client'
import { clsx } from 'clsx'

interface Props { title: string; subtitle?: string }

const WINDOW_DAYS = 30

function AlertBell() {
  const navigate = useNavigate()
  const { filters } = useSharedSearch()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const { data } = useQuery({
    queryKey: ['alerts', filters.condition, filterParams(filters)],
    queryFn: () => api.getAlerts({ ...filterParams(filters), days: WINDOW_DAYS }),
    enabled: filters.condition.trim().length >= 2,
    staleTime: 5 * 60 * 1000,
  })

  // Close on outside click.
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const count = data?.count ?? 0
  // Handles full ISO ("YYYY-MM-DD" → DD/MM) and partial ("YYYY-MM" → MM/YYYY).
  const fmt = (d?: string | null) => {
    if (!d) return '—'
    return d.length >= 10 ? `${d.slice(8, 10)}/${d.slice(5, 7)}` : d.length >= 7 ? `${d.slice(5, 7)}/${d.slice(0, 4)}` : d
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)}
        aria-label={`New trials alerts (${count})`}
        className="w-8 h-8 rounded-lg hover:bg-iq-bg flex items-center justify-center text-iq-muted hover:text-iq-navy transition-colors relative">
        <Bell className="w-4 h-4" />
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[15px] h-[15px] px-1 rounded-full bg-iq-orange text-white text-[9px] font-bold flex items-center justify-center">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-10 w-80 glass rounded-xl shadow-card-md border border-iq-border z-[1000] overflow-hidden"
          >
            <div className="px-4 py-3 border-b border-iq-border flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-iq-navy flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-iq-orange" /> New Trials
                </p>
                <p className="text-[10px] text-iq-muted mt-0.5">
                  {count.toLocaleString()} newly registered for <span className="text-iq-blue">{filters.condition}</span> · last {WINDOW_DAYS} days
                </p>
              </div>
              <button onClick={() => setOpen(false)} className="text-iq-muted hover:text-iq-navy">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="max-h-[360px] overflow-y-auto">
              {!data ? (
                <div className="p-4 space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-12 bg-iq-bg rounded animate-pulse" />)}
                </div>
              ) : data.trials.length === 0 ? (
                <p className="px-4 py-6 text-[11px] text-iq-muted text-center">
                  No new trials for this indication in the last {WINDOW_DAYS} days.
                </p>
              ) : (
                data.trials.map(t => (
                  <div key={t.nctId}
                    onClick={() => { setOpen(false); navigate(`/protocol/${t.nctId}`) }}
                    className="px-4 py-2.5 border-b border-iq-border hover:bg-iq-bg cursor-pointer group transition-colors">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-[10px] font-mono text-iq-blue">{t.nctId}</span>
                      <span className="text-[10px] text-iq-muted flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-iq-orange" /> {fmt(t.firstPostDate)}
                      </span>
                    </div>
                    <p className="text-[11px] text-iq-text line-clamp-1 mb-1">{t.title}</p>
                    <div className="flex items-center gap-1.5">
                      <Badge value={t.phase} type="phase" />
                      <Badge value={t.status} type="status" />
                      <ChevronRight className="w-3 h-3 text-iq-border group-hover:text-iq-blue ml-auto transition-colors" />
                    </div>
                  </div>
                ))
              )}
            </div>

            {data && data.count > data.trials.length && (
              <div className="px-4 py-2 border-t border-iq-border text-center">
                <span className="text-[10px] text-iq-muted">Showing newest {data.trials.length} of {data.count.toLocaleString()}</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function TopBar({ title, subtitle }: Props) {
  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-iq-border bg-white flex-shrink-0">
      <div>
        <h1 className="font-bold text-iq-navy text-base leading-none">{title}</h1>
        {subtitle && <p className="text-[11px] text-iq-muted mt-0.5">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-1">
        <button aria-label="Help"
          className="w-8 h-8 rounded-lg hover:bg-iq-bg flex items-center justify-center text-iq-muted hover:text-iq-navy transition-colors">
          <HelpCircle className="w-4 h-4" />
        </button>
        <AlertBell />
        <div className="w-8 h-8 rounded-lg bg-iq-navy flex items-center justify-center ml-1 cursor-pointer">
          <User className="w-3.5 h-3.5 text-white" />
        </div>
      </div>
    </header>
  )
}
