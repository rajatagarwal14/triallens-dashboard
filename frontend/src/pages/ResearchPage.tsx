import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, Label, CartesianGrid,
} from 'recharts'
import {
  Search, Lightbulb, CalendarClock, Clock, OctagonX, Users2,
  Sparkles, Trophy, Globe, Gauge,
} from 'lucide-react'
import { TopBar } from '@/components/Layout/TopBar'
import { CoverageBadge } from '@/components/common/CoverageBadge'
import { ErrorState } from '@/components/common/ErrorState'
import { SkeletonChart } from '@/components/common/SkeletonCard'
import { ActiveFilters } from '@/components/common/ActiveFilters'
import { api } from '@/api/client'
import { useSharedSearch, filterParams } from '@/context/SearchContext'
import type { Insight } from '@/types'

const TOOLTIP_STYLE = {
  background: '#FFFFFF', border: '1px solid #D2DADF', borderRadius: 8,
  color: '#2B3A42', boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
}

const INSIGHT_ICON: Record<string, any> = {
  trend: CalendarClock, latestage: Trophy, geo: Globe, feasibility: Gauge,
  risk: OctagonX, enrollment: Users2, sponsors: Users2,
}

// IQVIA phase palette for the readout-forecast stacked bars.
const PHASE_COLORS: Record<string, string> = {
  EARLY_PHASE1: '#7FA9C3', PHASE1: '#005487', PHASE2: '#00A3E0',
  PHASE3: '#6CC04A', PHASE4: '#FE8A12', NA: '#B0BEC5',
}

function InsightCard({ insight, i }: { insight: Insight; i: number }) {
  const Icon = INSIGHT_ICON[insight.kind] ?? Lightbulb
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
      className="glass rounded-xl p-4 flex gap-3">
      <div className="w-8 h-8 rounded-lg bg-iq-blue/10 flex items-center justify-center flex-shrink-0">
        <Icon className="w-4 h-4 text-iq-blue" />
      </div>
      <div>
        <p className="text-xs font-semibold text-iq-navy mb-0.5">{insight.title}</p>
        <p className="text-[11px] text-iq-muted leading-relaxed">{insight.detail}</p>
      </div>
    </motion.div>
  )
}

export function ResearchPage() {
  const { filters, setFilters } = useSharedSearch()
  const condition = filters.condition
  const [input, setInput] = useState(condition)

  const params = filterParams(filters)
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['research', params],
    queryFn: () => api.getResearch(params),
  })

  const analyze = (c: string) => { const v = c.trim(); if (v.length >= 2) setFilters({ condition: v }) }

  const readout = data?.readoutForecast
  const readoutPhases = readout?.phases ?? []
  const readoutData = readout?.byYear ?? []

  const maxMonths = Math.max(...(data?.timeToCompletion ?? []).map(t => t.medianMonths), 1)
  const maxEnroll = Math.max(...(data?.enrollmentBenchmarks ?? []).map(e => e.median), 1)
  const maxRate = Math.max(...(data?.enrollmentRate ?? []).map(e => e.perSiteMonth), 0.01)
  const maxCountry = data?.countryActivity?.top?.[0]?.trials ?? 1

  return (
    <div className="flex flex-col h-full bg-iq-bg">
      <TopBar title="Research" subtitle="Planning insights · trial completions · feasibility benchmarks" />

      <div className="flex-1 overflow-y-auto p-6 pb-10 space-y-4">
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

        <ActiveFilters />

        {isError && <ErrorState compact error={error} onRetry={() => refetch()} />}
        {!isLoading && !isError && data && <CoverageBadge coverage={data.coverage} />}

        {/* Insights */}
        <div>
          <p className="section-title flex items-center gap-1.5"><Lightbulb className="w-3.5 h-3.5 text-iq-orange" /> Key Insights</p>
          {isLoading ? (
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, i) => <div key={i} className="glass rounded-xl h-20 animate-pulse" />)}
            </div>
          ) : (data?.insights.length ?? 0) === 0 ? (
            <p className="text-xs text-iq-muted">Not enough data to generate insights for this query.</p>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {data!.insights.map((ins, i) => <InsightCard key={ins.title} insight={ins} i={i} />)}
            </div>
          )}
        </div>

        {/* Expected trial readouts by year */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
          <div className="flex items-center justify-between mb-1">
            <p className="section-title mb-0 flex items-center gap-1.5"><CalendarClock className="w-3.5 h-3.5 text-iq-blue" /> Anticipated Trial Completions by Year</p>
            <span className="text-[10px] text-iq-muted bg-green-50 text-green-700 border border-green-200 px-2 py-1 rounded-full">based on registered completion dates</span>
          </div>
          <p className="text-[10px] text-iq-muted mb-2">
            Number of trials scheduled to reach their <strong>primary completion</strong> (final data collection for the primary outcome measure)
            in each upcoming year, by phase. Based on registered completion dates — plan around when key competitor studies finish.
          </p>
          <p className="text-[10px] text-iq-muted mb-3 flex flex-wrap gap-x-3 gap-y-0.5">
            {readoutPhases.map(p => (
              <span key={p} className="inline-flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm" style={{ background: PHASE_COLORS[p] ?? '#B0BEC5' }} />
                {readout?.phaseLabels[p] ?? p}
              </span>
            ))}
          </p>
          {isLoading ? <SkeletonChart height={230} /> : readoutData.length === 0 ? (
            <p className="text-xs text-iq-muted py-8 text-center">No scheduled completion dates for this indication.</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={230}>
                <BarChart data={readoutData} margin={{ top: 8, right: 12, left: 12, bottom: 4 }}>
                  <CartesianGrid stroke="#E8EEF3" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="year" tick={{ fill: '#6B7A85', fontSize: 11 }} axisLine={{ stroke: '#D2DADF' }} tickLine={false} />
                  <YAxis tick={{ fill: '#6B7A85', fontSize: 10 }} axisLine={false} tickLine={false} width={44}>
                    <Label value="Number of Trials" angle={-90} position="insideLeft" offset={0} fill="#6B7A85" fontSize={10} style={{ textAnchor: 'middle' }} />
                  </YAxis>
                  <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgba(0,163,224,0.05)' }}
                    formatter={(v: number, name: string) => [v, readout?.phaseLabels[name] ?? name]} />
                  {readoutPhases.map(p => (
                    <Bar key={p} dataKey={p} stackId="r" fill={PHASE_COLORS[p] ?? '#B0BEC5'} radius={[0, 0, 0, 0]} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[11px] font-bold text-iq-navy text-center mt-2">Year of Primary Completion Date</p>
              <p className="text-[9px] text-iq-muted text-center mt-0.5">Y-axis: Number of Trials · stacked by phase</p>
            </>
          )}
        </motion.div>

        {/* Benchmarks row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Time to completion */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
            <p className="section-title flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-iq-navy" /> Time to Completion</p>
            {isLoading ? <SkeletonChart height={180} /> : (
              <div className="space-y-2.5">
                {(data?.timeToCompletion ?? []).map(t => (
                  <div key={t.phase}>
                    <div className="flex justify-between mb-1">
                      <span className="text-[11px] text-iq-text">{t.phase}</span>
                      <span className="text-[11px] font-semibold text-iq-navy">{t.medianMonths} mo</span>
                    </div>
                    <div className="bg-iq-bg border border-iq-border rounded-full h-1.5">
                      <div className="h-full rounded-full bg-iq-navy" style={{ width: `${(t.medianMonths / maxMonths) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
            <p className="text-[9px] text-iq-muted mt-3">Median months, start → primary completion</p>
          </motion.div>

          {/* Trial discontinuation rate */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
            <p className="section-title flex items-center gap-1.5"><OctagonX className="w-3.5 h-3.5 text-iq-orange" /> Trial Discontinuation Rate</p>
            {isLoading ? <SkeletonChart height={180} /> : (
              <div className="space-y-2.5">
                {(data?.discontinuation ?? []).map(a => (
                  <div key={a.phase}>
                    <div className="flex justify-between mb-1">
                      <span className="text-[11px] text-iq-text">{a.phase}</span>
                      <span className="text-[11px] font-semibold text-iq-navy" title={`${a.dropped} of ${a.total} trials stopped early`}>{a.rate}%</span>
                    </div>
                    <div className="bg-iq-bg border border-iq-border rounded-full h-1.5">
                      <div className="h-full rounded-full" style={{ width: `${a.rate}%`, background: a.rate >= 10 ? '#EF4444' : '#FE8A12' }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
            <p className="text-[9px] text-iq-muted mt-3">% of trials stopped early — terminated, withdrawn, or suspended before completion</p>
          </motion.div>

          {/* Enrollment size benchmarks */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
            <p className="section-title flex items-center gap-1.5"><Users2 className="w-3.5 h-3.5 text-iq-green" /> Enrollment Size</p>
            {isLoading ? <SkeletonChart height={180} /> : (
              <div className="space-y-2.5">
                {(data?.enrollmentBenchmarks ?? []).map(e => (
                  <div key={e.phase}>
                    <div className="flex justify-between mb-1">
                      <span className="text-[11px] text-iq-text">{e.phase}</span>
                      <span className="text-[11px] font-semibold text-iq-navy">{e.median.toLocaleString()}</span>
                    </div>
                    <div className="bg-iq-bg border border-iq-border rounded-full h-1.5">
                      <div className="h-full rounded-full bg-iq-green" style={{ width: `${(e.median / maxEnroll) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
            <p className="text-[9px] text-iq-muted mt-3">Median target enrollment per trial (patients)</p>
          </motion.div>
        </div>

        {/* Feasibility row: enrollment pace + geographic activity */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Enrollment feasibility (pace) */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
            <p className="section-title flex items-center gap-1.5"><Gauge className="w-3.5 h-3.5 text-iq-blue" /> Enrollment Feasibility (Pace)</p>
            {isLoading ? <SkeletonChart height={160} /> : (data?.enrollmentRate.length ?? 0) === 0 ? (
              <p className="text-xs text-iq-muted py-6 text-center">Not enough site/date data to compute pace.</p>
            ) : (
              <div className="space-y-2.5">
                {(data?.enrollmentRate ?? []).map(e => (
                  <div key={e.phase}>
                    <div className="flex justify-between mb-1">
                      <span className="text-[11px] text-iq-text">{e.phase}</span>
                      <span className="text-[11px] font-semibold text-iq-navy">{e.perSiteMonth} <span className="text-iq-muted font-normal">pts/site/mo</span></span>
                    </div>
                    <div className="bg-iq-bg border border-iq-border rounded-full h-1.5">
                      <div className="h-full rounded-full bg-iq-blue" style={{ width: `${(e.perSiteMonth / maxRate) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
            <p className="text-[9px] text-iq-muted mt-3">Median patients enrolled per site per month — size site counts &amp; timelines against this</p>
          </motion.div>

          {/* Geographic activity */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl p-5">
            <div className="flex items-center justify-between">
              <p className="section-title mb-0 flex items-center gap-1.5"><Globe className="w-3.5 h-3.5 text-iq-navy" /> Geographic Activity</p>
              {data?.countryActivity && (
                <span className="text-[10px] text-iq-muted">{data.countryActivity.totalCountries} countries · top 3 = {data.countryActivity.top3Share}%</span>
              )}
            </div>
            {isLoading ? <SkeletonChart height={160} /> : (
              <div className="space-y-2 mt-3 max-h-[220px] overflow-y-auto pr-1">
                {(data?.countryActivity?.top ?? []).map((c, i) => (
                  <div key={c.country} className="flex items-center gap-3">
                    <span className="text-[10px] text-iq-muted w-4 text-right">{i + 1}</span>
                    <span className="text-[11px] text-iq-text w-32 truncate" title={c.country}>{c.country}</span>
                    <div className="flex-1 bg-iq-bg border border-iq-border rounded-full h-1.5">
                      <div className="h-full rounded-full bg-iq-navy" style={{ width: `${(c.trials / maxCountry) * 100}%` }} />
                    </div>
                    <span className="text-[11px] font-semibold text-iq-navy w-8 text-right">{c.trials}</span>
                  </div>
                ))}
              </div>
            )}
            <p className="text-[9px] text-iq-muted mt-3">Trials running per country — for country strategy &amp; site selection</p>
          </motion.div>
        </div>

        <div className="flex items-center gap-1.5 text-[10px] text-iq-muted">
          <Sparkles className="w-3 h-3 text-iq-blue" />
          All figures computed live from the analyzed ClinicalTrials.gov sample and update with your filters. Completion counts reflect registered primary completion dates.
        </div>
      </div>
    </div>
  )
}
