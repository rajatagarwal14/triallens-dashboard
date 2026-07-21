import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, Label,
} from 'recharts'
import { Search, CalendarClock, Building2, Trophy, ChevronRight, Sparkles } from 'lucide-react'
import { TopBar } from '@/components/Layout/TopBar'
import { Badge } from '@/components/common/Badge'
import { CoverageBadge } from '@/components/common/CoverageBadge'
import { ErrorState } from '@/components/common/ErrorState'
import { SkeletonChart } from '@/components/common/SkeletonCard'
import { ActiveFilters } from '@/components/common/ActiveFilters'
import { api } from '@/api/client'
import { useSharedSearch, filterParams } from '@/context/SearchContext'
import { clsx } from 'clsx'

const TOOLTIP_STYLE = {
  background: '#FFFFFF', border: '1px solid #D2DADF', borderRadius: 8,
  color: '#2B3A42', boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
}

const SPONSOR_CLASS_COLOR: Record<string, string> = {
  INDUSTRY: '#00A3E0', NIH: '#6CC04A', FED: '#005487', OTHER_GOV: '#7FA9C3',
  NETWORK: '#FFC107', INDIV: '#FE8A12', OTHER: '#7FA9C3',
}

type Granularity = 'month' | 'bimonth' | 'quarter'
const GRANULARITY_OPTIONS: { value: Granularity; label: string }[] = [
  { value: 'month', label: 'Monthly' },
  { value: 'bimonth', label: 'Bi-Monthly' },
  { value: 'quarter', label: 'Quarterly' },
]

function iso(d: Date) { return d.toISOString().slice(0, 10) }

// Quick presets for the completion date window.
function presets() {
  const now = new Date()
  const y = now.getFullYear()
  return [
    { label: 'Next 12 mo', from: iso(now), to: iso(new Date(now.getFullYear() + 1, now.getMonth(), now.getDate())) },
    { label: 'This year', from: `${y}-01-01`, to: `${y}-12-31` },
    { label: 'Next 2 yrs', from: iso(now), to: `${y + 2}-12-31` },
    { label: 'Anytime', from: '', to: '' },
  ]
}

export function CompetitionPage() {
  const navigate = useNavigate()
  const { filters, setFilters } = useSharedSearch()
  const condition = filters.condition
  const [input, setInput] = useState(condition)
  const [granularity, setGranularity] = useState<Granularity>('quarter')
  // Default to an UPCOMING window (today → +2 yrs) so "Upcoming Trial Completions"
  // actually leads with future catalysts, not trials that completed decades ago.
  const [from, setFrom] = useState(() => iso(new Date()))
  const [to, setTo] = useState(() => `${new Date().getFullYear() + 2}-12-31`)

  const params = { ...filterParams(filters), completionFrom: from || undefined, completionTo: to || undefined, granularity }

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['competition', params],
    queryFn: () => api.getCompetition(params),
  })

  const analyze = (c: string) => { const v = c.trim(); if (v.length >= 2) setFilters({ condition: v }) }

  const maxTimeline = Math.max(...(data?.timeline ?? []).map(t => t.count), 1)
  const maxTrials = data?.leaderboard?.[0]?.trials ?? 1
  const fmtDate = (d?: string | null) => d ? d.length >= 7 ? `${d.slice(5, 7)}/${d.slice(0, 4)}` : d : '—'
  const granularityLabel = GRANULARITY_OPTIONS.find(g => g.value === granularity)!.label

  return (
    <div className="flex flex-col h-full bg-iq-bg">
      <TopBar title="Competition" subtitle="Trial completion intelligence · who finishes when · sponsor landscape" />

      <div className="flex-1 overflow-y-auto p-6 pb-10 space-y-4">
        {/* Search + date window */}
        <div className="flex gap-3 flex-wrap">
          <div className="flex-1 min-w-[240px] relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-iq-muted" />
            <input className="input-dark pl-9" value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && analyze(input)}
              placeholder="Indication / condition…" />
          </div>
          <button onClick={() => analyze(input)} className="btn-primary">Analyze</button>
        </div>

        {/* Primary completion date window */}
        <div className="glass rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <CalendarClock className="w-4 h-4 text-iq-blue" />
            <p className="text-xs font-semibold text-iq-navy">Trial Completion Window</p>
            <span className="text-[10px] text-iq-muted">
              — filter trials by their primary completion date (when the trial's main results become available)
            </span>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <label className="flex items-center gap-1.5 text-[11px] text-iq-muted">
              From
              <input type="date" value={from} onChange={e => setFrom(e.target.value)}
                className="bg-iq-bg border border-iq-border rounded-lg px-2 py-1 text-xs text-iq-text focus:outline-none focus:border-iq-blue" />
            </label>
            <label className="flex items-center gap-1.5 text-[11px] text-iq-muted">
              To
              <input type="date" value={to} onChange={e => setTo(e.target.value)}
                className="bg-iq-bg border border-iq-border rounded-lg px-2 py-1 text-xs text-iq-text focus:outline-none focus:border-iq-blue" />
            </label>
            <div className="flex gap-1.5 ml-auto">
              {presets().map(p => {
                const active = from === p.from && to === p.to
                return (
                  <button key={p.label} onClick={() => { setFrom(p.from); setTo(p.to) }}
                    className={clsx('chip text-[11px] px-2 py-0.5', active ? 'chip-active' : 'chip-idle')}>
                    {p.label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        <ActiveFilters />

        {isError && <ErrorState compact error={error} onRetry={() => refetch()} />}

        {!isLoading && !isError && data && (
          <div className="flex items-center gap-2">
            <CoverageBadge coverage={data.coverage} />
            <span className="text-[10px] text-iq-muted">
              {data.readoutCount.toLocaleString()} trials with a completion date{(from || to) ? ' in window' : ''}
            </span>
          </div>
        )}

        {/* Trial completion timeline */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
          <div className="flex items-center justify-between mb-1">
            <p className="section-title mb-0">Trial Completion Timeline</p>
            <div className="flex glass rounded-lg overflow-hidden border border-iq-border">
              {GRANULARITY_OPTIONS.map(g => (
                <button key={g.value} onClick={() => setGranularity(g.value)}
                  className={clsx('px-2 py-1 text-[10px] font-medium transition-colors',
                    granularity === g.value ? 'bg-iq-blue/10 text-iq-navy' : 'text-iq-muted hover:text-iq-text')}>
                  {g.label}
                </button>
              ))}
            </div>
          </div>
          <p className="text-[10px] text-iq-muted mb-3">
            How many trials in this indication complete their primary endpoint in each {granularityLabel.toLowerCase()} period —
            use this to see when competitor studies are expected to finish.
          </p>
          {isLoading ? <SkeletonChart height={200} /> : (data?.timeline?.length ?? 0) === 0 ? (
            <p className="text-xs text-iq-muted py-8 text-center">No completion dates in this window.</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={215}>
                <BarChart data={data!.timeline} margin={{ top: 8, right: 8, left: 8, bottom: 4 }}>
                  {/* height=55 gives rotated labels room even for the longest string
                      ("Nov–Dec 2028" under Bi-Monthly) — a tighter value clipped the
                      bottom of longer labels against the SVG's own bounds. */}
                  <XAxis dataKey="period" tick={{ fill: '#6B7A85', fontSize: 9 }} axisLine={{ stroke: '#D2DADF' }}
                    tickLine={false} interval="preserveStartEnd" angle={-35} textAnchor="end" height={55} />
                  <YAxis tick={{ fill: '#6B7A85', fontSize: 10 }} axisLine={false} tickLine={false} width={50}>
                    <Label value="Trials" angle={-90} position="insideLeft" offset={-4} fill="#6B7A85" fontSize={10} style={{ textAnchor: 'middle' }} />
                  </YAxis>
                  <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgba(0,163,224,0.05)' }}
                    formatter={(v: number) => [v.toLocaleString(), 'Trials completing']} />
                  <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                    {data!.timeline.map((t, i) => (
                      <Cell key={i} fill={t.count >= maxTimeline * 0.75 ? '#005487' : '#00A3E0'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[10px] font-bold text-iq-navy text-center mt-1">
                X-axis: {granularityLabel} Period (Trial Primary Completion Date)
              </p>
              <p className="text-[9px] text-iq-muted text-center mt-0.5">
                Y-axis: Number of Trials Completing
              </p>
            </>
          )}
        </motion.div>

        <div className="grid grid-cols-2 gap-4">
          {/* Sponsor leaderboard */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
            <div className="flex items-center gap-1.5 mb-3">
              <Trophy className="w-3.5 h-3.5 text-iq-orange" />
              <p className="section-title mb-0">Sponsor Leaderboard</p>
            </div>
            <p className="text-[10px] text-iq-muted mb-3">
              Sponsors ranked by number of trials running in this indication + window.
            </p>
            {isLoading ? <SkeletonChart height={260} /> : (data?.leaderboard.length ?? 0) === 0 ? (
              <p className="text-xs text-iq-muted py-8 text-center">No sponsors for this indication + window.</p>
            ) : (
              <div className="space-y-2.5">
                {data!.leaderboard.map((s, i) => {
                  const pct = (s.trials / maxTrials) * 100
                  const color = SPONSOR_CLASS_COLOR[s.class] ?? '#7FA9C3'
                  return (
                    <div key={s.sponsor} className="flex items-start gap-2">
                      <span className="text-[10px] text-iq-muted w-4 text-right flex-shrink-0 mt-0.5">{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-0.5">
                          <span className="text-[11px] text-iq-text leading-tight line-clamp-2 flex-1 min-w-0" title={s.sponsor}>{s.sponsor}</span>
                        </div>
                        <div className="bg-iq-bg border border-iq-border rounded-full h-1.5 mb-1">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                        </div>
                        <p className="text-[10px] text-iq-muted">
                          <span className="font-semibold text-iq-navy">{s.trials} trial{s.trials !== 1 ? 's' : ''}</span>
                          {s.lateStage > 0 && (
                            <span className="text-iq-green"> · {s.lateStage} late-stage (Phase III/IV)</span>
                          )}
                        </p>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            <p className="text-[9px] text-iq-muted mt-3 flex items-center gap-1">
              <Building2 className="w-2.5 h-2.5" /> "Late-stage" trials (Phase III/IV) are closer to filing/approval — a nearer-term competitive threat than early-phase trials.
            </p>
          </motion.div>

          {/* Upcoming trial completions */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
            <div className="flex items-center gap-1.5 mb-3">
              <CalendarClock className="w-3.5 h-3.5 text-iq-blue" />
              <p className="section-title mb-0">Upcoming Trial Completions (soonest first)</p>
            </div>
            <p className="text-[10px] text-iq-muted mb-3">
              Trials expected to finish their primary endpoint soonest — i.e. whose results/data should become available next.
            </p>
            {isLoading ? <SkeletonChart height={260} /> : (data?.readouts.length ?? 0) === 0 ? (
              <p className="text-xs text-iq-muted py-8 text-center">No dated completions for this indication + window.</p>
            ) : (
              <div className="space-y-1.5 max-h-[360px] overflow-y-auto pr-1">
                {data!.readouts.map(r => (
                  <div key={r.nctId} onClick={() => navigate(`/protocol/${r.nctId}`)}
                    className="p-2.5 rounded-lg border border-iq-border hover:bg-iq-bg cursor-pointer group transition-colors">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-[10px] font-mono text-iq-blue">{r.nctId}</span>
                      <span className="text-[10px] font-semibold text-iq-navy flex items-center gap-1">
                        {fmtDate(r.primaryCompletionDate)}
                        <span className={clsx('text-[8px] px-1 py-0.5 rounded-full',
                          r.primaryCompletionType === 'ESTIMATED' ? 'bg-orange-50 text-orange-700' : 'bg-slate-100 text-slate-500')}
                          title={r.primaryCompletionType === 'ESTIMATED' ? 'Estimated completion date' : 'Actual/reported completion date'}>
                          {r.primaryCompletionType === 'ESTIMATED' ? 'Estimated' : 'Actual'}
                        </span>
                      </span>
                    </div>
                    <p className="text-[11px] text-iq-text line-clamp-2 leading-tight mb-1">{r.title}</p>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Badge value={r.phase} type="phase" />
                      <Badge value={r.status} type="status" />
                      <ChevronRight className="w-3 h-3 text-iq-border group-hover:text-iq-blue ml-auto transition-colors" />
                    </div>
                    <p className="text-[9px] text-iq-muted line-clamp-1" title={r.sponsor}>{r.sponsor}</p>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        </div>

        <div className="flex items-center gap-1.5 text-[10px] text-iq-muted">
          <Sparkles className="w-3 h-3 text-iq-blue" />
          Tip: "Estimated" completion dates are the sponsor's projected finish date (a future catalyst to watch) — "Actual" means the trial has already reported that milestone.
        </div>
      </div>
    </div>
  )
}
