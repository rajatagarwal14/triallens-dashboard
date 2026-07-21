import { useMemo, useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList,
} from 'recharts'
import { Layers, Pencil, Check, RotateCcw, Gauge, Clock, OctagonX, Sparkles } from 'lucide-react'
import { api } from '@/api/client'
import { clsx } from 'clsx'
import type { CohortGroup } from '@/types'

const GROUP_COLORS = ['#005487', '#00A3E0', '#FE8A12', '#6CC04A']

// A cohort-suggestion + comparison panel. Given the active filters it asks the
// backend to split the trials along one of several axes, then compares
// enrolment pace / duration / discontinuation across the suggested cohorts.
// Suggestions are editable — the user can switch axis, rename or drop a cohort.
export function CohortPanel({ params }: { params: Record<string, string | number | undefined> }) {
  const [axis, setAxis] = useState<string | undefined>(undefined)
  const [renames, setRenames] = useState<Record<string, string>>({})
  const [dropped, setDropped] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState<string | null>(null)

  const query = useMemo(() => ({ ...params, ...(axis ? { axis } : {}) }), [params, axis])
  const { data, isLoading, isError } = useQuery({
    queryKey: ['cohorts', query],
    queryFn: () => api.getCohorts(query),
  })

  // Reset per-cohort edits whenever the axis or the underlying search changes.
  useEffect(() => { setRenames({}); setDropped(new Set()); setEditing(null) }, [axis, params])

  const groups = (data?.groups ?? []).filter(g => !dropped.has(g.key))
  const nameOf = (g: CohortGroup) => renames[g.key] ?? g.label

  const paceData = groups
    .filter(g => g.enrollPacePerSiteMonth != null)
    .map((g, i) => ({ name: nameOf(g), value: g.enrollPacePerSiteMonth as number, key: g.key, idx: i }))

  return (
    <div className="glass rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-iq-border flex items-center gap-2 flex-wrap">
        <Layers className="w-4 h-4 text-iq-blue" />
        <p className="text-sm font-semibold text-iq-navy">Cohort Comparison</p>
        <span className="text-[10px] text-iq-muted">suggested groupings for this search — switch axis or edit below</span>
        {data && (
          <span className="ml-auto text-[10px] text-iq-muted flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-iq-orange" />
            auto-suggested: <span className="font-medium text-iq-navy">{data.availableAxes.find(a => a.key === data.suggestedAxis)?.label}</span>
          </span>
        )}
      </div>

      {/* Axis selector — only axes that actually split this set are enabled */}
      <div className="px-4 py-2.5 border-b border-iq-border flex items-center gap-1.5 flex-wrap">
        {(data?.availableAxes ?? []).map(a => (
          <button key={a.key} disabled={!a.applicable}
            onClick={() => setAxis(a.key)}
            title={a.applicable ? `${a.groupCount} groups` : 'only one group in this set'}
            className={clsx('text-[11px] px-2.5 py-1 rounded-full border transition-colors',
              (data?.axis === a.key)
                ? 'bg-iq-blue/10 text-iq-navy border-iq-blue/30 font-medium'
                : a.applicable
                  ? 'text-iq-muted border-iq-border hover:text-iq-navy hover:border-iq-blue/30'
                  : 'text-iq-border border-iq-border/50 cursor-not-allowed')}>
            {a.label}{a.applicable && <span className="ml-1 opacity-60">·{a.groupCount}</span>}
          </button>
        ))}
        {(Object.keys(renames).length > 0 || dropped.size > 0) && (
          <button onClick={() => { setRenames({}); setDropped(new Set()) }}
            className="ml-auto text-[10px] text-iq-muted hover:text-iq-navy flex items-center gap-1">
            <RotateCcw className="w-3 h-3" /> reset edits
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="p-8 flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-iq-blue border-t-transparent rounded-full animate-spin" />
        </div>
      ) : isError || !data ? (
        <p className="px-4 py-8 text-xs text-iq-muted text-center">Could not build cohorts for this search.</p>
      ) : groups.length === 0 ? (
        <p className="px-4 py-8 text-xs text-iq-muted text-center">No cohorts to show — all groups dropped.</p>
      ) : (
        <div className="p-4 space-y-4">
          {/* Enrolment-pace comparison chart */}
          {paceData.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-iq-navy mb-1">Enrolment pace by cohort</p>
              <p className="text-[10px] text-iq-muted mb-2">median patients enrolled per site per month — higher accrues faster</p>
              <ResponsiveContainer width="100%" height={Math.max(120, paceData.length * 46)}>
                <BarChart data={paceData} layout="vertical" margin={{ left: 8, right: 40, top: 4, bottom: 4 }}>
                  <XAxis type="number" tick={{ fontSize: 10, fill: '#6B7A85' }} axisLine={{ stroke: '#D2DADF' }} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 10, fill: '#005487' }}
                    axisLine={false} tickLine={false} />
                  <Tooltip
                    formatter={(v: number) => [`${v} pts/site/mo`, 'Pace']}
                    contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #D2DADF' }} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={26}>
                    {paceData.map(d => <Cell key={d.key} fill={GROUP_COLORS[d.idx % GROUP_COLORS.length]} />)}
                    <LabelList dataKey="value" position="right" style={{ fontSize: 10, fill: '#6B7A85' }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Editable cohort cards with the full feasibility panel */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {groups.map((g, i) => (
              <div key={g.key} className="bg-iq-bg border border-iq-border rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <span className="w-2.5 h-2.5 rounded-full flex-shrink-0 mt-1" style={{ background: GROUP_COLORS[i % GROUP_COLORS.length] }} />
                  <div className="flex-1 min-w-0">
                    {editing === g.key ? (
                      <div className="flex items-center gap-1">
                        <input autoFocus defaultValue={nameOf(g)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') { setRenames(r => ({ ...r, [g.key]: (e.target as HTMLInputElement).value })); setEditing(null) }
                            if (e.key === 'Escape') setEditing(null)
                          }}
                          className="text-[12px] font-semibold text-iq-navy bg-white border border-iq-blue/40 rounded px-1.5 py-0.5 w-full focus:outline-none" />
                        <button onClick={() => setEditing(null)} className="text-iq-blue"><Check className="w-3.5 h-3.5" /></button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <p className="text-[12px] font-semibold text-iq-navy leading-tight">{nameOf(g)}</p>
                        <button onClick={() => setEditing(g.key)} className="text-iq-muted hover:text-iq-navy"><Pencil className="w-2.5 h-2.5" /></button>
                        <span className="text-[10px] text-iq-muted ml-auto">{g.trialCount} trials</span>
                        <button onClick={() => setDropped(d => new Set(d).add(g.key))}
                          className="text-[10px] text-iq-muted hover:text-red-500" title="drop this cohort">×</button>
                      </div>
                    )}
                    <p className="text-[9px] text-iq-muted mt-0.5 leading-snug">{g.definition}</p>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-1.5 mt-2.5">
                  <Metric icon={Gauge} label="Pace" value={g.enrollPacePerSiteMonth != null ? `${g.enrollPacePerSiteMonth}` : '—'} sub={g.enrollPaceN ? `n=${g.enrollPaceN}` : 'no data'} />
                  <Metric icon={Clock} label="Duration" value={g.medianDurationMonths != null ? `${g.medianDurationMonths}mo` : '—'} sub="median" />
                  <Metric icon={OctagonX} label="Discont." value={`${g.discontinuationRate}%`} sub={`${g.discontinued} stopped`} />
                </div>
              </div>
            ))}
          </div>

          <p className="text-[9px] text-iq-muted leading-snug">
            Pace = median patients per site per month (a feasibility proxy from enrolment ÷ sites ÷ months). Cohorts are auto-suggested from the search and eligibility text; rename or drop any that don't fit your read.
          </p>
        </div>
      )}
    </div>
  )
}

function Metric({ icon: Icon, label, value, sub }: { icon: any; label: string; value: string; sub: string }) {
  return (
    <div className="bg-white border border-iq-border rounded-md px-2 py-1.5">
      <div className="flex items-center gap-1 text-iq-muted"><Icon className="w-2.5 h-2.5" /><span className="text-[8px] uppercase tracking-wide">{label}</span></div>
      <p className="text-[13px] font-bold text-iq-navy leading-tight mt-0.5">{value}</p>
      <p className="text-[8px] text-iq-muted leading-none">{sub}</p>
    </div>
  )
}
