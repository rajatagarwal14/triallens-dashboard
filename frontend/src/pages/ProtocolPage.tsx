import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, Search, FlaskConical, Users, Calendar, Globe,
  Cpu, CheckCircle, XCircle, ChevronRight, Tag,
  AlertTriangle, Building2, Zap, Scale,
} from 'lucide-react'
import { TopBar } from '@/components/Layout/TopBar'
import { Badge } from '@/components/common/Badge'
import { ErrorState } from '@/components/common/ErrorState'
import { api } from '@/api/client'
import type { Study, SimilarStudy } from '@/types'
import { clsx } from 'clsx'

function ComplexityGauge({ score }: { score: number }) {
  const pct = (score / 10) * 100
  const color = score < 4 ? '#10b981' : score < 7 ? '#f59e0b' : '#ef4444'
  const label = score < 4 ? 'Low' : score < 7 ? 'Medium' : 'High'

  return (
    <div className="flex items-center gap-3">
      <div className="relative w-16 h-16">
        <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="#E8EEF3" strokeWidth="3" />
          <motion.circle
            cx="18" cy="18" r="15.5" fill="none"
            stroke={color} strokeWidth="3"
            strokeDasharray={`${pct * 0.974} 97.4`}
            strokeLinecap="round"
            initial={{ strokeDasharray: '0 97.4' }}
            animate={{ strokeDasharray: `${pct * 0.974} 97.4` }}
            transition={{ duration: 1, ease: 'easeOut' }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold" style={{ color }}>{score.toFixed(1)}</span>
        </div>
      </div>
      <div>
        <p className="text-xs font-semibold" style={{ color }}>{label} Complexity</p>
        <p className="text-[10px] text-iq-muted">Protocol restrictiveness score</p>
        <p className="text-[9px] text-iq-muted mt-0.5">Scale: 0 (open) → 10 (very restrictive)</p>
      </div>
    </div>
  )
}

function SimilarCard({ similar, index, onClick }: { similar: SimilarStudy; index: number; onClick: () => void }) {
  const score = similar.score
  const barColor = score > 0.7 ? '#10b981' : score > 0.4 ? '#3b82f6' : '#64748b'

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04 }}
      onClick={onClick}
      className="glass glass-hover rounded-lg p-4 cursor-pointer border border-iq-border"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-mono text-brand">{similar.study.nctId}</p>
          <p className="text-xs text-iq-text line-clamp-2 mt-0.5 leading-relaxed">{similar.study.title}</p>
        </div>
        <div className="flex-shrink-0 text-right">
          <p className="text-base font-bold" style={{ color: barColor }}>{Math.round(score * 100)}%</p>
          <p className="text-[9px] text-iq-muted">match</p>
        </div>
      </div>

      {/* Score bar */}
      <div className="bg-iq-bg rounded-full h-1 mb-2.5">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score * 100}%` }}
          transition={{ delay: index * 0.04 + 0.2, duration: 0.6 }}
          className="h-full rounded-full"
          style={{ background: barColor }}
        />
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <Badge value={similar.study.phases[0] ?? 'NA'} type="phase" />
        <Badge value={similar.study.status} type="status" />
        {similar.sharedConditions.slice(0, 1).map(c => (
          <span key={c} className="text-[9px] bg-brand/10 text-brand px-1.5 py-0.5 rounded-full border border-brand/20">{c}</span>
        ))}
      </div>
    </motion.div>
  )
}

function EligibilityPanel({ nctId }: { nctId: string }) {
  const [tab, setTab] = useState<'inclusion' | 'exclusion' | 'extracted'>('extracted')
  const { data, isLoading } = useQuery({
    queryKey: ['eligibility', nctId],
    queryFn: () => api.getEligibility(nctId),
  })

  const extracted = data?.extracted

  return (
    <div className="glass rounded-xl overflow-hidden">
      <div className="flex items-center gap-0 border-b border-iq-border">
        {(['extracted', 'inclusion', 'exclusion'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={clsx(
              'flex-1 px-4 py-3 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5',
              tab === t ? 'bg-brand/10 text-brand border-b-2 border-brand' : 'text-iq-muted hover:text-iq-text',
            )}>
            {t === 'extracted' && <Cpu className="w-3 h-3" />}
            {t === 'inclusion' && <CheckCircle className="w-3 h-3" />}
            {t === 'exclusion' && <XCircle className="w-3 h-3" />}
            {t === 'extracted' ? 'Structured Extraction' : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      <div className="p-4">
        {isLoading ? (
          <div className="space-y-2 animate-pulse">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-3 bg-iq-bg rounded" style={{ width: `${60 + i * 8}%` }} />
            ))}
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {tab === 'extracted' && extracted && (
              <motion.div key="extracted" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="space-y-4">
                <ComplexityGauge score={extracted.complexityScore} />

                {/* Restrictiveness vs the market (H) */}
                {data?.market && (
                  <div className="bg-iq-bg rounded-lg p-3 border border-iq-border">
                    <div className="flex items-center justify-between mb-1.5">
                      <p className="text-[10px] text-iq-muted flex items-center gap-1">
                        <Scale className="w-3 h-3" /> Restrictiveness vs market
                      </p>
                      <span className={clsx('text-[11px] font-bold',
                        data.market.percentile >= 50 ? 'text-red-500' : 'text-iq-green')}>
                        {data.market.percentile >= 50 ? 'More' : 'Less'} restrictive than {data.market.percentile >= 50 ? data.market.percentile : 100 - data.market.percentile}%
                      </span>
                    </div>
                    <div className="relative bg-white border border-iq-border rounded-full h-2">
                      <div className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-iq-green via-iq-orange to-red-400"
                        style={{ width: `${data.market.percentile}%` }} />
                      <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-0.5 h-3 bg-iq-navy"
                        style={{ left: `${Math.min(98, Math.max(2, data.market.percentile))}%` }} />
                    </div>
                    <p className="text-[9px] text-iq-muted mt-1.5">
                      This protocol scores {data.market.myScore.toFixed(1)} vs a market median of {data.market.marketMedian.toFixed(1)}
                      {' '}across {data.market.peerCount} {data.market.condition} trials.
                    </p>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                  {/* Age range */}
                  <div className="bg-iq-bg rounded-lg p-3 border border-iq-border">
                    <p className="text-[10px] text-iq-muted mb-1.5 flex items-center gap-1">
                      <Users className="w-3 h-3" /> Age Range
                    </p>
                    <p className="text-sm font-semibold text-iq-navy">
                      {extracted.ageRange.min ?? '?'} – {extracted.ageRange.max ?? '?'} yrs
                    </p>
                  </div>

                  {/* Sex */}
                  <div className="bg-iq-bg rounded-lg p-3 border border-iq-border">
                    <p className="text-[10px] text-iq-muted mb-1.5">Sex Eligibility</p>
                    <p className="text-sm font-semibold text-iq-navy capitalize">
                      {data?.study?.eligibility?.sex?.toLowerCase() ?? 'All'}
                    </p>
                  </div>
                </div>

                {/* Biomarkers */}
                {extracted.biomarkers.length > 0 && (
                  <div>
                    <p className="text-[10px] text-iq-muted mb-2 flex items-center gap-1">
                      <Tag className="w-3 h-3" /> Biomarkers Detected
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {extracted.biomarkers.map(b => (
                        <span key={b} className="px-2 py-0.5 rounded-md text-[11px] font-mono font-semibold
                          bg-violet-50 text-violet-700 border border-violet-200">
                          {b}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Excluded biomarkers — rule-outs, not selection markers */}
                {(extracted.biomarkersExcluded?.length ?? 0) > 0 && (
                  <div>
                    <p className="text-[10px] text-iq-muted mb-2 flex items-center gap-1">
                      <Tag className="w-3 h-3" /> Biomarker Rule-outs (exclusion)
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {extracted.biomarkersExcluded.map(b => (
                        <span key={b} className="px-2 py-0.5 rounded-md text-[11px] font-mono font-semibold
                          bg-red-50 text-red-700 border border-red-200 line-through decoration-red-400">
                          {b}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Disease stage */}
                {extracted.diseaseStage.length > 0 && (
                  <div>
                    <p className="text-[10px] text-iq-muted mb-2">Disease Stage / Setting</p>
                    <div className="flex flex-wrap gap-1.5">
                      {extracted.diseaseStage.map(s => (
                        <span key={s} className="px-2 py-0.5 rounded-md text-[11px] bg-orange-50 text-orange-700 border border-orange-200">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Prior treatment */}
                {extracted.priorTreatment.length > 0 && (
                  <div>
                    <p className="text-[10px] text-iq-muted mb-2">Prior Treatment Signals</p>
                    <div className="space-y-1">
                      {extracted.priorTreatment.map((t, i) => (
                        <p key={i} className="text-[11px] text-iq-muted flex items-start gap-1.5">
                          <span className="text-brand mt-0.5">·</span>{t}
                        </p>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-2 pt-2 border-t border-iq-border">
                  <Cpu className="w-3.5 h-3.5 text-brand flex-shrink-0" />
                  <p className="text-[10px] text-iq-muted">
                    Protocol Intelligence · NLP extraction + biomarker detection
                  </p>
                </div>
              </motion.div>
            )}

            {tab === 'inclusion' && (
              <motion.div key="inclusion" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <p className="text-[11px] text-iq-text whitespace-pre-wrap leading-relaxed">
                  {extracted?.inclusionText || data?.study?.eligibility?.criteria || 'No criteria available'}
                </p>
              </motion.div>
            )}

            {tab === 'exclusion' && (
              <motion.div key="exclusion" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <p className="text-[11px] text-iq-text whitespace-pre-wrap leading-relaxed">
                  {extracted?.exclusionText || 'No exclusion criteria extracted'}
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}

function LookupPanel() {
  const [input, setInput] = useState('')
  const navigate = useNavigate()
  return (
    <div className="flex flex-col h-full items-center justify-center p-8">
      <div className="w-14 h-14 rounded-2xl bg-brand/10 border border-brand/20 flex items-center justify-center mb-4">
        <FlaskConical className="w-6 h-6 text-brand" />
      </div>
      <h2 className="text-lg font-bold text-iq-navy mb-2">Protocol Analyzer</h2>
      <p className="text-sm text-iq-muted text-center max-w-xs mb-6">
        Enter an NCT ID to deep-dive a trial — eligibility NLP extraction, complexity scoring, and similar trial ranking
      </p>
      <div className="flex gap-2 w-full max-w-xs">
        <input
          className="input-dark flex-1 font-mono"
          placeholder="NCT01234567"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && input.trim() && navigate(`/protocol/${input.trim()}`)}
        />
        <button onClick={() => input.trim() && navigate(`/protocol/${input.trim()}`)} className="btn-primary px-3">
          <Search className="w-4 h-4" />
        </button>
      </div>
      <p className="text-[11px] text-iq-muted mt-4">Or click any trial in Discovery Studio to analyze it</p>
    </div>
  )
}

export function ProtocolPage() {
  const { nctId } = useParams<{ nctId?: string }>()
  const navigate = useNavigate()

  const { data: similar, isLoading: simLoading, isError, error, refetch } = useQuery({
    queryKey: ['similar', nctId],
    queryFn: () => api.getSimilar(nctId!),
    enabled: !!nctId,
  })

  const study = similar?.target

  if (!nctId) return (
    <div className="flex flex-col h-full">
      <TopBar title="Protocol Analyzer" subtitle="Deep-dive any trial · eligibility NLP · similarity scoring" />
      <LookupPanel />
    </div>
  )

  return (
    <div className="flex flex-col h-full">
      <TopBar title="Protocol Analyzer" subtitle={nctId} />

      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {/* Back */}
        <button onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-xs text-iq-muted hover:text-iq-text transition-colors">
          <ArrowLeft className="w-3.5 h-3.5" /> Back
        </button>

        {isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : simLoading || !study ? (
          <div className="space-y-4">
            <div className="glass rounded-xl h-32 animate-pulse" />
            <div className="grid grid-cols-2 gap-4">
              <div className="glass rounded-xl h-64 animate-pulse" />
              <div className="glass rounded-xl h-64 animate-pulse" />
            </div>
          </div>
        ) : (
          <>
            {/* Trial header */}
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className="glass rounded-xl p-5 glow-border">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className="font-mono text-sm font-bold text-brand">{study.nctId}</span>
                    {study.phases.map(p => <Badge key={p} value={p} type="phase" size="md" />)}
                    <Badge value={study.status} type="status" size="md" />
                  </div>
                  <h2 className="text-base font-bold text-iq-navy leading-snug">{study.title}</h2>
                  <p className="text-xs text-iq-muted mt-1 line-clamp-2">{study.summary}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t border-iq-border">
                <div>
                  <p className="text-[10px] text-iq-muted mb-1 flex items-center gap-1">
                    <Building2 className="w-3 h-3" /> Sponsor
                  </p>
                  <p className="text-xs font-semibold text-iq-text">{study.sponsor.name}</p>
                  <p className="text-[10px] text-iq-muted">{study.sponsor.class}</p>
                </div>
                <div>
                  <p className="text-[10px] text-iq-muted mb-1 flex items-center gap-1">
                    <Users className="w-3 h-3" /> Enrollment Target
                  </p>
                  <p className="text-sm font-bold text-iq-navy">
                    {study.enrollment?.count?.toLocaleString() ?? '—'}
                  </p>
                  <p className="text-[10px] text-iq-muted">{study.enrollment?.type}</p>
                </div>
                <div>
                  <p className="text-[10px] text-iq-muted mb-1 flex items-center gap-1">
                    <Calendar className="w-3 h-3" /> Timeline
                  </p>
                  <p className="text-xs text-iq-text">{study.startDate ?? '—'}</p>
                  <p className="text-[10px] text-iq-muted">→ {study.completionDate ?? '—'}</p>
                </div>
                <div>
                  <p className="text-[10px] text-iq-muted mb-1 flex items-center gap-1">
                    <Globe className="w-3 h-3" /> Geographic Reach
                  </p>
                  <p className="text-sm font-bold text-iq-navy">{study.countryCount} countries</p>
                  <p className="text-[10px] text-iq-muted">{study.siteCount} sites</p>
                </div>
              </div>

              {study.interventions.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {study.interventions.slice(0, 6).map((iv, i) => (
                    <span key={i} className="text-[11px] px-2 py-0.5 rounded-full bg-iq-bg border border-iq-border text-iq-text">
                      <span className="text-iq-muted mr-1">{iv.type}</span>{iv.name}
                    </span>
                  ))}
                </div>
              )}
            </motion.div>

            {/* Two-column: Eligibility + Similar */}
            <div className="grid grid-cols-2 gap-4">
              {/* Eligibility NLP */}
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
                <p className="section-title mb-2">Eligibility Intelligence</p>
                <EligibilityPanel nctId={study.nctId} />
              </motion.div>

              {/* Similar trials */}
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
                <div className="flex items-center justify-between mb-2">
                  <p className="section-title mb-0">Similar Trials</p>
                  <div className="flex items-center gap-1 text-[10px] text-iq-muted">
                    <Zap className="w-3 h-3" /> TF-IDF cosine similarity
                  </div>
                </div>
                <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                  {simLoading
                    ? Array.from({ length: 5 }).map((_, i) => (
                        <div key={i} className="glass rounded-lg h-20 animate-pulse" />
                      ))
                    : similar?.similar.length === 0
                      ? (
                          <div className="glass rounded-xl p-6 text-center">
                            <AlertTriangle className="w-6 h-6 text-iq-muted mx-auto mb-2" />
                            <p className="text-xs text-iq-muted">No similar trials found for this condition</p>
                          </div>
                        )
                      : similar?.similar.map((s, i) => (
                          <SimilarCard
                            key={s.study.nctId}
                            similar={s}
                            index={i}
                            onClick={() => navigate(`/protocol/${s.study.nctId}`)}
                          />
                        ))
                  }
                </div>
              </motion.div>
            </div>

            {/* Conditions tag cloud */}
            {study.conditions.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                className="glass rounded-xl p-4">
                <p className="section-title">Conditions & Keywords</p>
                <div className="flex flex-wrap gap-2">
                  {[...study.conditions, ...study.keywords].slice(0, 20).map((t, i) => (
                    <span key={i} className="chip chip-idle text-[11px]">{t}</span>
                  ))}
                </div>
              </motion.div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
