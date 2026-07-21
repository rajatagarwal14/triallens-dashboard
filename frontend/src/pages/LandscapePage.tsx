import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, ComposedChart, Area, Line, LineChart, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceDot, Brush, CartesianGrid,
} from 'recharts'
import { TrendingUp, Users, Globe, Building2, Award, Search, MousePointerClick } from 'lucide-react'
import { TopBar } from '@/components/Layout/TopBar'
import { useSharedSearch, filterParams } from '@/context/SearchContext'
import { ActiveFilters } from '@/components/common/ActiveFilters'
import { AnimatedNumber } from '@/components/common/AnimatedNumber'
import { clsx } from 'clsx'
import { SkeletonStatCard, SkeletonChart } from '@/components/common/SkeletonCard'
import { CoverageBadge } from '@/components/common/CoverageBadge'
import { ErrorState } from '@/components/common/ErrorState'
import { api } from '@/api/client'
import { CohortPanel } from '@/components/cohorts/CohortPanel'

// IQVIA-palette phase colors
const PHASE_COLORS: Record<string, string> = {
  PHASE1:      '#005487',
  EARLY_PHASE1:'#7FA9C3',
  PHASE2:      '#00A3E0',
  PHASE3:      '#6CC04A',
  PHASE4:      '#FE8A12',
  NA:          '#B0BEC5',
}
const PHASE_LABELS: Record<string, string> = {
  PHASE1: 'Phase I', EARLY_PHASE1: 'Early I',
  PHASE2: 'Phase II', PHASE3: 'Phase III', PHASE4: 'Phase IV', NA: 'N/A',
}

const STATUS_COLORS: Record<string, string> = {
  RECRUITING:              '#6CC04A',
  ACTIVE_NOT_RECRUITING:   '#00A3E0',
  COMPLETED:               '#7FA9C3',
  TERMINATED:              '#EF4444',
  WITHDRAWN:               '#FE8A12',
  SUSPENDED:               '#F59E0B',
  ENROLLING_BY_INVITATION: '#005487',
  UNKNOWN:                 '#B0BEC5',
  NO_LONGER_AVAILABLE:     '#E11D48',
  APPROVED_FOR_MARKETING:  '#0D9488',
  AVAILABLE:               '#84CC16',
  TEMPORARILY_NOT_AVAILABLE: '#CA8A04',
  WITHHELD:                '#78716C',
}

const SPONSOR_COLORS: Record<string, string> = {
  INDUSTRY: '#00A3E0',
  NIH:      '#6CC04A',
  FED:      '#005487',
  OTHER:    '#7FA9C3',
  INDIV:    '#FE8A12',
  NETWORK:  '#FFC107',
}

const TOOLTIP_STYLE = {
  background: '#FFFFFF',
  border: '1px solid #D2DADF',
  borderRadius: 8,
  color: '#2B3A42',
  boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
}

function VelocityTooltip({ active, payload }: { active?: boolean; payload?: any[] }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as { year: string; count: number; avg: number | null; yoy: number | null }
  return (
    <div style={TOOLTIP_STYLE} className="px-3 py-2 text-xs">
      <p className="font-semibold text-iq-navy mb-1">{d.year}</p>
      <p className="text-iq-text">{d.count.toLocaleString()} trials started</p>
      {d.yoy !== null && (
        <p className={d.yoy >= 0 ? 'text-iq-green' : 'text-red-500'}>
          {d.yoy >= 0 ? '▲' : '▼'} {Math.abs(d.yoy)}% vs prior year
        </p>
      )}
      {d.avg !== null && <p className="text-iq-muted">avg {d.avg.toLocaleString()} patients/trial</p>}
    </div>
  )
}

function StatCard({ icon: Icon, label, value, sub, color = '#00A3E0', delay = 0 }: {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>
  label: string; value: number; sub?: string; color?: string; delay?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="stat-card"
    >
      <div className="flex items-start justify-between mb-3">
        <p className="text-xs text-iq-muted font-medium">{label}</p>
        <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${color}18` }}>
          <Icon className="w-3.5 h-3.5" style={{ color }} />
        </div>
      </div>
      <AnimatedNumber value={value} className="text-2xl font-bold text-iq-navy" />
      {sub && <p className="text-xs text-iq-muted mt-1">{sub}</p>}
    </motion.div>
  )
}

export function LandscapePage() {
  const navigate = useNavigate()
  const { filters, setFilters } = useSharedSearch()
  const condition = filters.condition
  const [input, setInput] = useState(condition)
  const [velMode, setVelMode] = useState<'total' | 'phase' | 'sponsor'>('total')

  const params = filterParams(filters)
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['landscape', params],
    queryFn: () => api.getLandscape(params),
  })

  // Analyze a new indication here — updates the shared condition (keeps filters).
  const analyze = (c: string) => {
    const v = c.trim()
    if (v.length < 2) return
    setFilters({ condition: v })
  }

  // Deep-link into Discovery with the merged filter set, and push the same merge
  // into shared context so Geo/Competition/Sites reflect it too.
  const goToDiscovery = (merged: typeof filters) => {
    const sp = new URLSearchParams()
    Object.entries(filterParams(merged)).forEach(([k, v]) => {
      if (v !== undefined && v !== '') sp.set(k, String(v))
    })
    navigate(`/?${sp.toString()}`)
  }

  // Clicking a chart segment ADDS the clicked value into that dimension's existing
  // multi-select — it never replaces/wipes out other values already active from
  // Discovery. This is a refine-in, not a reset.
  const addToFilter = (key: 'phases' | 'statuses' | 'sponsorClasses', value: string) => {
    const current = filters[key] as string[]
    const next = current.includes(value) ? current : [...current, value]
    const merged = { ...filters, [key]: next }
    setFilters({ [key]: next } as any)
    goToDiscovery(merged)
  }

  // Country is a single-select filter in Discovery, so clicking a country row
  // sets it directly (there's no multi-select array to preserve for this one).
  const drillCountry = (country: string) => {
    const merged = { ...filters, country }
    setFilters({ country })
    goToDiscovery(merged)
  }

  // Keep the raw CT.gov key on each datum so clicks map back to a filter value.
  const phaseData = Object.entries(data?.phaseCounts ?? {}).map(([k, v]) => ({
    key: k, name: PHASE_LABELS[k] ?? k, value: v, color: PHASE_COLORS[k] ?? '#B0BEC5',
  }))

  const statusData = Object.entries(data?.statusCounts ?? {})
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => ({
      key: k,
      name: k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      value: v,
      fill: STATUS_COLORS[k] ?? '#B0BEC5',
    }))

  // Enrollment velocity: trials started per year + avg trial size, with YoY %.
  // Honor the active look-back filter so the axis floor matches what's applied.
  const yearFloor = filters.fromYear ?? 2010
  const rawYears = Object.entries(data?.yearCounts ?? {})
    .filter(([y]) => !isNaN(+y) && +y >= yearFloor)
    .sort((a, b) => +a[0] - +b[0])
  const velocityRange = filters.fromYear ? `${filters.fromYear}–Present` : '2010–Present'
  const enrollByYear = data?.enrollmentByYear ?? {}
  const yearData = rawYears.map(([year, count], i) => {
    const prev = i > 0 ? rawYears[i - 1][1] : null
    const yoy = prev && prev > 0 ? Math.round(((count - prev) / prev) * 100) : null
    return { year, count, avg: enrollByYear[year] ?? null, yoy }
  })
  const peak = yearData.reduce<{ year: string; count: number } | null>(
    (m, d) => (!m || d.count > m.count ? { year: d.year, count: d.count } : m), null
  )

  // Velocity segmentation (G): total, or split by phase / sponsor type.
  const segSource = velMode === 'phase' ? data?.yearByPhase : velMode === 'sponsor' ? data?.yearBySponsor : null
  const segKeys = segSource
    ? Array.from(new Set(Object.values(segSource).flatMap(v => Object.keys(v))))
        .sort((a, b) => {
          const sum = (k: string) => Object.values(segSource!).reduce((t, v) => t + (v[k] ?? 0), 0)
          return sum(b) - sum(a)
        }).slice(0, 6)
    : []
  const segData = segSource
    ? rawYears.map(([year]) => ({ year, ...Object.fromEntries(segKeys.map(k => [k, segSource![year]?.[k] ?? 0])) }))
    : []
  const segColor = (k: string) => PHASE_COLORS[k] ?? SPONSOR_COLORS[k] ?? '#7FA9C3'
  const segLabel = (k: string) => PHASE_LABELS[k] ?? k

  const topCountries = Object.entries(data?.countryCounts ?? {}).slice(0, 10)
    .map(([country, count]) => ({ country, count }))

  const recruiting = data?.statusCounts?.RECRUITING ?? 0
  const completed  = data?.statusCounts?.COMPLETED ?? 0

  return (
    <div className="flex flex-col h-full bg-iq-bg">
      <TopBar title="Historical" subtitle="Competitive intelligence and enrollment trends" />

      <div className="flex-1 overflow-y-auto p-6 pb-10 space-y-4">
        {/* Search bar */}
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-iq-muted" />
            <input
              className="input-dark pl-9"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && analyze(input)}
              placeholder="Indication / condition…"
            />
          </div>
          <button onClick={() => analyze(input)} className="btn-primary">
            Analyze
          </button>
        </div>

        {isError && <ErrorState compact error={error} onRetry={() => refetch()} />}

        <ActiveFilters />

        {!isLoading && !isError && data && (
          <div className="flex items-center gap-2">
            <CoverageBadge coverage={data.coverage} />
            {!data.coverage.isComplete && (
              <span className="text-[10px] text-iq-muted">
                Narrow the search (e.g. a subtype or drug) for full-dataset charts
              </span>
            )}
          </div>
        )}

        {/* KPI row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => <SkeletonStatCard key={i} />)
            : <>
                <StatCard icon={Globe}      label="Total Trials"   value={data?.totalCount ?? 0}   sub="in ClinicalTrials.gov" color="#00A3E0" delay={0} />
                <StatCard icon={TrendingUp} label="Recruiting"     value={recruiting}               sub="actively enrolling"   color="#6CC04A" delay={0.05} />
                <StatCard icon={Users}      label="Avg Enrollment" value={data?.avgEnrollment ?? 0} sub="patients per trial"   color="#005487" delay={0.1} />
                <StatCard icon={Building2}  label="Completed"      value={completed}                sub="historical trials"    color="#FE8A12" delay={0.15} />
              </>
          }
        </div>

        {/* Charts row 1 */}
        <div className="grid grid-cols-2 gap-4">
          {/* Phase distribution */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            className="glass rounded-xl p-5">
            <div className="flex items-center justify-between">
              <p className="section-title mb-0">Phase Distribution</p>
              <span className="text-[9px] text-iq-muted flex items-center gap-1"><MousePointerClick className="w-2.5 h-2.5" /> click to filter</span>
            </div>
            {isLoading ? <SkeletonChart height={160} /> : (
              <>
                <ResponsiveContainer width="100%" height={130}>
                  <PieChart>
                    <Pie data={phaseData} cx="50%" cy="50%" innerRadius={40} outerRadius={60}
                      dataKey="value" paddingAngle={2} animationBegin={0} animationDuration={800}
                      className="cursor-pointer"
                      onClick={(e: any) => e?.key && addToFilter('phases', e.key)}>
                      {phaseData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} strokeWidth={0} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [v.toLocaleString(), 'Trials']} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-wrap gap-x-3 gap-y-1 justify-center">
                  {phaseData.map((entry) => (
                    <span key={entry.name} className="flex items-center gap-1 text-[10px] text-iq-muted whitespace-nowrap">
                      <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: entry.color }} />
                      {entry.name}
                    </span>
                  ))}
                </div>
              </>
            )}
          </motion.div>

          {/* Status breakdown */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
            className="glass rounded-xl p-5">
            <div className="flex items-center justify-between">
              <p className="section-title mb-0">Status Breakdown</p>
              <span className="text-[9px] text-iq-muted flex items-center gap-1"><MousePointerClick className="w-2.5 h-2.5" /> click to filter</span>
            </div>
            {isLoading ? <SkeletonChart height={220} /> : (
              // Height scales with category count — CT.gov now has up to 13 distinct
              // statuses, and a fixed height crowded rows so wrapped multi-word labels
              // (e.g. "Approved For Marketing") overlapped into neighboring bars.
              <ResponsiveContainer width="100%" height={Math.max(160, statusData.length * 28)}>
                <BarChart data={statusData} layout="vertical" barCategoryGap="25%">
                  <XAxis type="number" tick={{ fill: '#6B7A85', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" tick={{ fill: '#6B7A85', fontSize: 9 }} width={130}
                    axisLine={false} tickLine={false} interval={0} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgba(0,163,224,0.04)' }} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} className="cursor-pointer" maxBarSize={16}
                    onClick={(e: any) => e?.key && addToFilter('statuses', e.key)}>
                    {statusData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </motion.div>
        </div>

        {/* Enrollment velocity */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="glass rounded-xl p-5">
          <div className="flex items-center justify-between mb-1">
            <p className="section-title mb-0">Enrollment Velocity — Trial Start Dates ({velocityRange})</p>
            <div className="flex items-center gap-2">
              {/* Segmentation toggle (G) */}
              <div className="flex glass rounded-lg overflow-hidden border border-iq-border">
                {(['total', 'phase', 'sponsor'] as const).map(m => (
                  <button key={m} onClick={() => setVelMode(m)}
                    className={clsx('px-2 py-1 text-[10px] font-medium capitalize transition-colors',
                      velMode === m ? 'bg-iq-blue/10 text-iq-navy' : 'text-iq-muted hover:text-iq-text')}>
                    {m === 'sponsor' ? 'Sponsor' : m}
                  </button>
                ))}
              </div>
              {peak && velMode === 'total' && (
                <span className="text-[10px] text-iq-navy bg-iq-blue/10 px-2 py-1 rounded-full border border-iq-blue/20">
                  Peak {peak.year} · {peak.count.toLocaleString()}
                </span>
              )}
            </div>
          </div>
          <p className="text-[10px] text-iq-muted mb-1">
            {velMode === 'total' ? (
              <>
                <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-iq-blue" /> Trials initiated / year</span>
                <span className="inline-flex items-center gap-1 ml-3"><span className="w-2 h-0.5 bg-iq-orange" /> Avg trial size (patients)</span>
              </>
            ) : (
              <span className="inline-flex flex-wrap gap-x-3 gap-y-0.5">
                {segKeys.map(k => (
                  <span key={k} className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: segColor(k) }} /> {segLabel(k)}</span>
                ))}
                <span className="text-iq-muted">· trials initiated / year by {velMode}</span>
              </span>
            )}
          </p>
          <p className="text-[9px] text-iq-muted mb-3 flex items-center gap-1">
            <MousePointerClick className="w-2.5 h-2.5" /> Drag the handles below the chart to zoom into a specific year range
          </p>
          {isLoading ? <SkeletonChart height={260} /> : velMode !== 'total' ? (
            <>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={segData} margin={{ top: 8, right: 16, left: 8, bottom: 4 }}>
                  <CartesianGrid stroke="#E8EEF3" strokeDasharray="3 3" vertical={true} />
                  <XAxis dataKey="year" tick={{ fill: '#6B7A85', fontSize: 9 }} axisLine={{ stroke: '#D2DADF' }}
                    tickLine={false} interval={0} angle={-45} textAnchor="end" height={44} />
                  <YAxis tick={{ fill: '#6B7A85', fontSize: 10 }} axisLine={false} tickLine={false}
                    width={40} tickCount={7} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  {segKeys.map(k => (
                    <Line key={k} type="monotone" dataKey={k} name={segLabel(k)} stroke={segColor(k)} strokeWidth={2}
                      dot={false} animationDuration={800} />
                  ))}
                  <Brush dataKey="year" height={20} stroke="#00A3E0" fill="#F2F5F8" travellerWidth={8}
                    className="text-[9px]" />
                </LineChart>
              </ResponsiveContainer>
              <p className="text-[11px] font-bold text-iq-navy text-center mt-2">Year (Trial Start Date)</p>
              <p className="text-[9px] text-iq-muted text-center mt-0.5">Y-axis: Trials Initiated</p>
            </>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={yearData} margin={{ top: 8, right: 16, left: 8, bottom: 4 }}>
                  <defs>
                    <linearGradient id="velFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00A3E0" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#00A3E0" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#E8EEF3" strokeDasharray="3 3" vertical={true} />
                  <XAxis dataKey="year" tick={{ fill: '#6B7A85', fontSize: 9 }} axisLine={{ stroke: '#D2DADF' }}
                    tickLine={false} interval={0} angle={-45} textAnchor="end" height={44} />
                  <YAxis yAxisId="left" tick={{ fill: '#6B7A85', fontSize: 10 }} axisLine={false} tickLine={false}
                    width={40} tickCount={7} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fill: '#FE8A12', fontSize: 10 }} axisLine={false}
                    tickLine={false} width={48} tickCount={7} />
                  <Tooltip content={<VelocityTooltip />} cursor={{ stroke: 'rgba(0,163,224,0.3)' }} />
                  <Area yAxisId="left" type="monotone" dataKey="count" stroke="#00A3E0" strokeWidth={2}
                    fill="url(#velFill)"
                    dot={{ fill: '#00A3E0', r: 2.5, strokeWidth: 0 }}
                    activeDot={{ r: 5, fill: '#005487', strokeWidth: 0 }}
                    animationDuration={1200} animationEasing="ease-out" />
                  <Line yAxisId="right" type="monotone" dataKey="avg" stroke="#FE8A12" strokeWidth={1.5}
                    strokeDasharray="4 3" dot={false} connectNulls
                    animationDuration={1200} />
                  {peak && (
                    <ReferenceDot yAxisId="left" x={peak.year} y={peak.count} r={4}
                      fill="#005487" stroke="#FFFFFF" strokeWidth={1.5} />
                  )}
                  <Brush dataKey="year" height={20} stroke="#00A3E0" fill="#F2F5F8" travellerWidth={8}
                    className="text-[9px]" />
                </ComposedChart>
              </ResponsiveContainer>
              <p className="text-[11px] font-bold text-iq-navy text-center mt-2">Year (Trial Start Date)</p>
              <p className="text-[9px] text-iq-muted text-center mt-0.5">
                <span className="text-iq-blue font-medium">Left Y-axis: Trials Initiated</span>
                &nbsp;·&nbsp;
                <span className="text-iq-orange font-medium">Right Y-axis: Avg Enrollment (patients)</span>
              </p>
            </>
          )}
        </motion.div>

        {/* Cohort comparison — suggested groupings for the current search */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.32 }}>
          <CohortPanel params={params} />
        </motion.div>

        {/* Top countries + sponsor split */}
        <div className="grid grid-cols-2 gap-4">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}
            className="glass rounded-xl p-5">
            <div className="flex items-center justify-between">
              <p className="section-title mb-0">Top Countries by Trial Activity</p>
              <span className="text-[9px] text-iq-muted flex items-center gap-1"><MousePointerClick className="w-2.5 h-2.5" /> click to filter</span>
            </div>
            {isLoading ? <SkeletonChart height={200} /> : (
              <div className="space-y-2 mt-2">
                {topCountries.map(({ country, count }, i) => {
                  const max = topCountries[0]?.count ?? 1
                  const pct = (count / max) * 100
                  return (
                    <div key={country} onClick={() => drillCountry(country)}
                      className="flex items-center gap-3 cursor-pointer rounded-md px-1 -mx-1 py-0.5 hover:bg-iq-bg transition-colors">
                      <span className="text-[10px] text-iq-muted w-4 text-right">{i + 1}</span>
                      <span className="text-xs text-iq-text w-32 truncate" title={country}>{country}</span>
                      <div className="flex-1 bg-iq-bg rounded-full h-1.5 border border-iq-border">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ delay: 0.4 + i * 0.04, duration: 0.6 }}
                          className="h-full rounded-full"
                          style={{ background: '#00A3E0' }}
                        />
                      </div>
                      <span className="text-[11px] font-semibold text-iq-navy w-8 text-right">{count}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
            className="glass rounded-xl p-5">
            <div className="flex items-center justify-between">
              <p className="section-title mb-0">Sponsor Type Split</p>
              <span className="text-[9px] text-iq-muted flex items-center gap-1"><MousePointerClick className="w-2.5 h-2.5" /> click to filter</span>
            </div>
            {isLoading ? <SkeletonChart height={200} /> : (
              <>
                <div className="space-y-3 mb-4 mt-2">
                  {Object.entries(data?.sponsorClassCounts ?? {}).map(([cls, count]) => {
                    const total = Object.values(data?.sponsorClassCounts ?? {}).reduce((a, b) => a + b, 0)
                    const pct = total > 0 ? Math.round((count / total) * 100) : 0
                    const color = SPONSOR_COLORS[cls] ?? '#7FA9C3'
                    return (
                      <div key={cls} onClick={() => addToFilter('sponsorClasses', cls)}
                        className="cursor-pointer rounded-md px-1 -mx-1 py-0.5 hover:bg-iq-bg transition-colors">
                        <div className="flex justify-between mb-1">
                          <span className="text-xs text-iq-muted">{cls}</span>
                          <span className="text-xs font-semibold text-iq-navy">{pct}%</span>
                        </div>
                        <div className="bg-iq-bg border border-iq-border rounded-full h-1.5">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${pct}%` }}
                            transition={{ duration: 0.8 }}
                            className="h-full rounded-full"
                            style={{ background: color }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
                <div className="flex items-center gap-1.5 pt-3 border-t border-iq-border">
                  <Award className="w-3.5 h-3.5 text-iq-blue" />
                  <p className="text-[10px] text-iq-muted">
                    Industry-sponsored trials dominate Phase II–IV in most oncology indications
                  </p>
                </div>
              </>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  )
}
