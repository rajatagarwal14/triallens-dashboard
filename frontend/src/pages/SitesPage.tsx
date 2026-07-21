import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Search, Building2, UserRound, MapPin, Activity, Users2, ChevronRight, Award,
} from 'lucide-react'
import { TopBar } from '@/components/Layout/TopBar'
import { CoverageBadge } from '@/components/common/CoverageBadge'
import { ErrorState } from '@/components/common/ErrorState'
import { SkeletonChart } from '@/components/common/SkeletonCard'
import { ActiveFilters } from '@/components/common/ActiveFilters'
import { api } from '@/api/client'
import { useSharedSearch, filterParams } from '@/context/SearchContext'
import { clsx } from 'clsx'
import type { SiteRow, InvestigatorRow } from '@/types'

// Enrolment rate = % of this site's / investigator's trials that are actively
// recruiting right now. Green when actively enrolling, muted when dormant.
function EnrollRate({ rate }: { rate: number }) {
  const active = rate > 0
  return (
    <span
      className={clsx(
        'text-[9px] font-semibold px-1.5 py-0.5 rounded-full whitespace-nowrap flex-shrink-0 border',
        active ? 'bg-green-50 text-green-700 border-green-200' : 'bg-iq-bg text-iq-muted border-iq-border',
      )}
      title="Share of this entity's trials currently open for enrolment (recruiting)"
    >
      {rate}% enrolling
    </span>
  )
}

function SiteCard({ s, rank, max, onOpen }: { s: SiteRow; rank: number; max: number; onOpen: () => void }) {
  return (
    <div onClick={onOpen}
      className="px-3 py-2.5 border-b border-iq-border hover:bg-iq-bg cursor-pointer group transition-colors">
      <div className="flex items-start gap-2">
        <span className="text-[10px] text-iq-muted w-4 text-right flex-shrink-0 mt-0.5">{rank}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <span className="text-[11px] font-medium text-iq-text leading-tight line-clamp-2 flex-1 min-w-0" title={s.facility}>{s.facility}</span>
            <span className="text-[11px] font-bold text-iq-navy flex-shrink-0">{s.trials} trials</span>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] text-iq-muted flex items-center gap-0.5"><MapPin className="w-2.5 h-2.5" />{[s.city, s.country].filter(Boolean).join(', ') || '—'}</span>
            {s.recruiting > 0 && <span className="text-[9px] text-iq-green">{s.recruiting} recruiting</span>}
          </div>
          <div className="mt-1 bg-iq-bg border border-iq-border rounded-full h-1">
            <div className="h-full rounded-full bg-iq-blue" style={{ width: `${(s.trials / max) * 100}%` }} />
          </div>
          <div className="flex items-center justify-between gap-2 mt-1">
            <span className="text-[9px] text-iq-muted">avg enrollment {s.avgEnrollment.toLocaleString()} · {s.enrollment.toLocaleString()} total</span>
            <EnrollRate rate={s.enrollRate} />
          </div>
        </div>
        <ChevronRight className="w-3 h-3 text-iq-border group-hover:text-iq-blue flex-shrink-0 mt-1 transition-colors" />
      </div>
    </div>
  )
}

function PICard({ p, rank, onOpen }: { p: InvestigatorRow; rank: number; onOpen: () => void }) {
  return (
    <div onClick={onOpen}
      className="px-3 py-2.5 border-b border-iq-border hover:bg-iq-bg cursor-pointer group transition-colors">
      <div className="flex items-start gap-2">
        <div className="w-6 h-6 rounded-full bg-iq-blue/10 flex items-center justify-center flex-shrink-0 mt-0.5">
          <UserRound className="w-3 h-3 text-iq-blue" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <span className="text-[11px] font-medium text-iq-text leading-tight line-clamp-2 flex-1 min-w-0" title={p.name}>{p.name}</span>
            <span className="text-[11px] font-bold text-iq-navy flex-shrink-0">{p.trials}</span>
          </div>
          {p.affiliation && <p className="text-[10px] text-iq-muted line-clamp-2 leading-tight" title={p.affiliation}>{p.affiliation}</p>}
          <div className="flex flex-wrap gap-1 mt-1">
            {p.focus.slice(0, 2).map(f => (
              <span key={f} className="text-[9px] bg-iq-blue/10 text-iq-navy border border-iq-blue/20 px-1.5 py-0.5 rounded-full truncate max-w-[130px]">{f}</span>
            ))}
          </div>
          <div className="flex items-center justify-between gap-2 mt-1">
            <span className="text-[9px] text-iq-muted">avg enrollment {p.avgEnrollment.toLocaleString()} across {p.trials} trial{p.trials !== 1 ? 's' : ''}</span>
            <EnrollRate rate={p.enrollRate} />
          </div>
        </div>
        <span className="text-[9px] text-iq-muted flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity self-center">
          view <ChevronRight className="w-3 h-3" />
        </span>
      </div>
    </div>
  )
}

export function SitesPage() {
  const navigate = useNavigate()
  const { filters, setFilters } = useSharedSearch()
  const condition = filters.condition
  const [input, setInput] = useState(condition)
  const [tab, setTab] = useState<'sites' | 'investigators'>('sites')

  const params = filterParams(filters)
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['sites', params],
    queryFn: () => api.getSites(params),
  })

  const analyze = (c: string) => { const v = c.trim(); if (v.length >= 2) setFilters({ condition: v }) }
  const maxSiteTrials = data?.sites?.[0]?.trials ?? 1

  return (
    <div className="flex flex-col h-full bg-iq-bg">
      <TopBar title="Sites & Investigators" subtitle="Site-activity database · investigator experience scorecards" />

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

        {!isLoading && !isError && data && (
          <div className="flex items-center gap-3 flex-wrap">
            <CoverageBadge coverage={data.coverage} />
            <span className="text-[10px] text-iq-muted">
              {data.siteUniverse.toLocaleString()} distinct sites · {data.investigatorUniverse.toLocaleString()} investigators in sample
            </span>
          </div>
        )}

        {/* KPI cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="stat-card">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-iq-muted">Active Sites</p>
              <Building2 className="w-4 h-4 text-iq-blue" />
            </div>
            <p className="text-2xl font-bold text-iq-navy">{isLoading ? '…' : data?.siteUniverse.toLocaleString()}</p>
            <p className="text-[10px] text-iq-muted mt-1">distinct facilities</p>
          </div>
          <div className="stat-card">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-iq-muted">Investigators</p>
              <Users2 className="w-4 h-4 text-iq-green" />
            </div>
            <p className="text-2xl font-bold text-iq-navy">{isLoading ? '…' : data?.investigatorUniverse.toLocaleString()}</p>
            <p className="text-[10px] text-iq-muted mt-1">named principal investigators</p>
          </div>
          <div className="stat-card">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-iq-muted">Top Site Volume</p>
              <Activity className="w-4 h-4 text-iq-orange" />
            </div>
            <p className="text-2xl font-bold text-iq-navy">{isLoading ? '…' : (data?.sites?.[0]?.trials ?? 0)}</p>
            <p className="text-[10px] text-iq-muted mt-1 line-clamp-2 leading-tight" title={data?.sites?.[0]?.facility}>{data?.sites?.[0]?.facility ?? 'trials at busiest site'}</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2">
          {([['sites', 'Site Activity', Building2], ['investigators', 'Investigator Scorecards', UserRound]] as const).map(([t, label, Icon]) => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx('flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors',
                tab === t ? 'bg-iq-blue/10 text-iq-navy border border-iq-blue/20' : 'text-iq-muted hover:text-iq-text border border-transparent')}>
              <Icon className="w-3.5 h-3.5" /> {label}
            </button>
          ))}
        </div>

        {tab === 'sites' ? (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-iq-border flex items-center gap-1.5">
              <Award className="w-3.5 h-3.5 text-iq-orange" />
              <p className="text-sm font-semibold text-iq-navy">Site-Activity Leaderboard</p>
              <span className="text-[10px] text-iq-muted ml-auto">ranked by trials run · then enrollment handled</span>
            </div>
            {isLoading ? <div className="p-5"><SkeletonChart height={300} /></div> : (data?.sites.length ?? 0) === 0 ? (
              <p className="px-4 py-8 text-xs text-iq-muted text-center">No geo-located sites in the analyzed sample.</p>
            ) : (
              data!.sites.map((s, i) => (
                <SiteCard key={s.facility + i} s={s} rank={i + 1} max={maxSiteTrials}
                  onOpen={() => navigate(`/protocol/${s.sampleNct}`)} />
              ))
            )}
          </motion.div>
        ) : (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-iq-border flex items-center gap-1.5">
              <Award className="w-3.5 h-3.5 text-iq-orange" />
              <p className="text-sm font-semibold text-iq-navy">Investigator Experience Scorecards</p>
              <span className="text-[10px] text-iq-muted ml-auto"># trials · therapeutic focus · enrollment track record</span>
            </div>
            {isLoading ? <div className="p-5"><SkeletonChart height={300} /></div> : (data?.investigators.length ?? 0) === 0 ? (
              <p className="px-4 py-8 text-xs text-iq-muted text-center">
                No named principal investigators in the analyzed sample (many industry trials list only a study director).
              </p>
            ) : (
              data!.investigators.map((p, i) => (
                <PICard key={p.name + i} p={p} rank={i + 1}
                  onOpen={() => navigate(`/protocol/${p.sampleNct}`)} />
              ))
            )}
          </motion.div>
        )}

        <p className="text-[10px] text-iq-muted">
          Built from public ClinicalTrials.gov site &amp; investigator records. Cross-referencing against an internal CTMS/site network (to flag high performers not yet engaged) would require that internal data source.
        </p>
      </div>
    </div>
  )
}
