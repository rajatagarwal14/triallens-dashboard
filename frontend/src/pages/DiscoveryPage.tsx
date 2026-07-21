import { useState, useCallback, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Search, SlidersHorizontal, X, ChevronRight, Users,
  Building2, MapPin, ArrowUpDown, Sparkles, Globe, Clock,
  FlaskConical, Briefcase, Info,
} from 'lucide-react'
import { TopBar } from '@/components/Layout/TopBar'
import { Badge } from '@/components/common/Badge'
import { SkeletonTableRow } from '@/components/common/SkeletonCard'
import { ErrorState } from '@/components/common/ErrorState'
import { AnimatedNumber } from '@/components/common/AnimatedNumber'
import { api } from '@/api/client'
import { useSharedSearch } from '@/context/SearchContext'
import type { PhaseFilter, StatusFilter, StudyType, SponsorClass, Study } from '@/types'
import { clsx } from 'clsx'

const PHASES: { value: PhaseFilter; label: string }[] = [
  { value: 'EARLY_PHASE1', label: 'Early I' },
  { value: 'PHASE1', label: 'Phase I' },
  { value: 'PHASE2', label: 'Phase II' },
  { value: 'PHASE3', label: 'Phase III' },
  { value: 'PHASE4', label: 'Phase IV' },
  { value: 'NA', label: 'N/A' },
]

const STATUSES: { value: StatusFilter; label: string; color: string }[] = [
  { value: 'RECRUITING',              label: 'Recruiting',          color: 'text-green-700' },
  { value: 'NOT_YET_RECRUITING',      label: 'Not Yet Recruiting',  color: 'text-sky-700' },
  { value: 'ENROLLING_BY_INVITATION', label: 'By Invitation',       color: 'text-violet-700' },
  { value: 'ACTIVE_NOT_RECRUITING',   label: 'Active (not recruit.)', color: 'text-blue-700' },
  { value: 'COMPLETED',               label: 'Completed',           color: 'text-slate-600' },
  { value: 'TERMINATED',              label: 'Terminated',          color: 'text-red-700' },
  { value: 'WITHDRAWN',               label: 'Withdrawn',           color: 'text-orange-700' },
  { value: 'SUSPENDED',               label: 'Suspended',           color: 'text-amber-700' },
  { value: 'UNKNOWN',                 label: 'Unknown',             color: 'text-gray-500' },
  { value: 'NO_LONGER_AVAILABLE',     label: 'No Longer Available', color: 'text-rose-700' },
  { value: 'APPROVED_FOR_MARKETING',  label: 'Approved for Marketing', color: 'text-teal-700' },
  { value: 'AVAILABLE',               label: 'Available (Expanded Access)', color: 'text-lime-700' },
  { value: 'TEMPORARILY_NOT_AVAILABLE', label: 'Temporarily Unavailable', color: 'text-yellow-700' },
  { value: 'WITHHELD',                label: 'Withheld',            color: 'text-stone-600' },
]

const STUDY_TYPES: { value: StudyType; label: string }[] = [
  { value: 'INTERVENTIONAL', label: 'Interventional' },
  { value: 'OBSERVATIONAL',  label: 'Observational' },
  { value: 'EXPANDED_ACCESS', label: 'Expanded Access' },
]

const SPONSOR_CLASSES: { value: SponsorClass; label: string }[] = [
  { value: 'INDUSTRY', label: 'Industry' },
  { value: 'NIH',      label: 'NIH' },
  { value: 'FED',      label: 'Government' },
  { value: 'NETWORK',  label: 'Network' },
  { value: 'OTHER',    label: 'Other' },
  { value: 'INDIV',    label: 'Individual' },
]

const LOOKBACK_OPTIONS = [
  { label: '1 yr', years: 1 },
  { label: '3 yr', years: 3 },
  { label: '5 yr', years: 5 },
  { label: '10 yr', years: 10 },
  { label: 'All time', years: null },
]

const QUICK_SEARCHES = [
  'Breast Cancer', 'AML', 'Lung Cancer', 'Multiple Myeloma',
  'Type 2 Diabetes', 'NSCLC', 'Melanoma', 'Alzheimer',
]

const SORT_PARAM: Record<string, string | undefined> = {
  relevance: undefined,
  enrollment: 'EnrollmentCount:desc',
  startDate:  'StartDate:desc',
  updated:    'LastUpdatePostDate:desc',
}

const COMMON_COUNTRIES = [
  'United States', 'Germany', 'France', 'United Kingdom', 'Japan',
  'China', 'Canada', 'Australia', 'Spain', 'Italy', 'Netherlands',
  'Belgium', 'Switzerland', 'South Korea', 'Brazil', 'India',
]

function currentYear() { return new Date().getFullYear() }

function FilterSection({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-iq-blue">{icon}</span>
        <span className="text-[10px] font-bold text-iq-muted uppercase tracking-widest">{title}</span>
      </div>
      {children}
    </div>
  )
}

function ChipGroup<T extends string>({
  options, selected, onToggle, colorFn,
}: {
  options: { value: T; label: string; color?: string }[]
  selected: T[]
  onToggle: (v: T) => void
  colorFn?: (v: T) => string
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map(o => {
        const active = selected.includes(o.value)
        return (
          <button key={o.value} onClick={() => onToggle(o.value)}
            className={clsx(
              'chip transition-all text-[11px] px-2 py-0.5',
              active ? 'chip-active' : 'chip-idle',
              active && colorFn ? colorFn(o.value) : '',
            )}>
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

function StudyRow({ study, onClick, index }: { study: Study; onClick: () => void; index: number }) {
  const phase = study.phases[0] ?? 'NA'
  const enrollment = study.enrollment?.count

  return (
    <motion.tr
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
      className="table-row group cursor-pointer"
      onClick={onClick}
    >
      <td className="px-3 py-3 font-mono text-[11px] text-iq-blue whitespace-nowrap">
        {study.nctId}
      </td>
      <td className="px-3 py-2.5">
        <p className="text-xs text-iq-text line-clamp-1 group-hover:text-iq-navy transition-colors leading-snug">{study.title}</p>
        <p className="text-[10px] text-iq-muted mt-0.5 line-clamp-1">
          {study.conditions.slice(0, 2).join(' · ')}
        </p>
      </td>
      <td className="px-3 py-2.5 whitespace-nowrap">
        <Badge value={phase} type="phase" />
      </td>
      <td className="px-3 py-2.5 whitespace-nowrap">
        <Badge value={study.status} type="status" />
      </td>
      <td className="px-3 py-2.5 whitespace-nowrap">
        <span className="text-[10px] text-iq-muted uppercase tracking-wide">
          {study.studyType?.slice(0, 4) || '—'}
        </span>
      </td>
      <td className="px-3 py-2.5">
        <p className="text-[11px] text-iq-text line-clamp-2 leading-tight max-w-[180px]" title={study.sponsor.name}>{study.sponsor.name}</p>
        <p className="text-[9px] text-iq-muted uppercase tracking-wide">{study.sponsor.class}</p>
      </td>
      <td className="px-3 py-2.5 text-right whitespace-nowrap">
        {enrollment ? (
          <span className="text-xs font-semibold text-iq-navy">{enrollment.toLocaleString()}</span>
        ) : (
          <span className="text-xs text-iq-muted">—</span>
        )}
      </td>
      <td className="px-3 py-2.5 text-center">
        <span className="text-xs text-iq-muted">{study.countryCount}</span>
      </td>
      <td className="px-2 py-2.5 text-right">
        <ChevronRight className="w-3.5 h-3.5 text-iq-border group-hover:text-iq-blue transition-colors ml-auto" />
      </td>
    </motion.tr>
  )
}

// Seed initial filter state from URL query params so Historical charts (and
// shareable links) can deep-link into a pre-filtered Discovery view.
function csvParam<T extends string>(sp: URLSearchParams, key: string): T[] {
  const raw = sp.get(key)
  return raw ? (raw.split(',').filter(Boolean) as T[]) : []
}

export function DiscoveryPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { filters: shared, setFilters: setSharedFilters } = useSharedSearch()

  // Seed from the URL when present (deep-link / chart drill), otherwise from the
  // shared context so navigating in from another page carries the active search.
  const hasUrl = searchParams.has('condition')
  const initialCondition = hasUrl ? (searchParams.get('condition') ?? '') : shared.condition
  const initialCountry = hasUrl ? (searchParams.get('country') ?? '') : shared.country
  const initialSort = (searchParams.get('sortBy') ?? 'relevance') as
    'relevance' | 'enrollment' | 'startDate' | 'updated'
  // Preserve the look-back across a chart drill: URL fromYear → lookback years.
  const urlFromYear = searchParams.get('fromYear')
  const initialLookback = urlFromYear ? currentYear() - +urlFromYear
    : shared.fromYear ? currentYear() - shared.fromYear : null

  const [input, setInput] = useState(initialCondition)
  const [condition, setCondition] = useState(initialCondition)
  const [phases, setPhases] = useState<PhaseFilter[]>(hasUrl ? csvParam(searchParams, 'phases') : shared.phases)
  const [statuses, setStatuses] = useState<StatusFilter[]>(hasUrl ? csvParam(searchParams, 'status') : shared.statuses)
  const [studyTypes, setStudyTypes] = useState<StudyType[]>(hasUrl ? csvParam(searchParams, 'studyTypes') : shared.studyTypes)
  const [sponsorClasses, setSponsorClasses] = useState<SponsorClass[]>(hasUrl ? csvParam(searchParams, 'sponsorClasses') : shared.sponsorClasses)
  const [country, setCountry] = useState(initialCountry)
  const [countryInput, setCountryInput] = useState(initialCountry)
  const [showCountrySuggest, setShowCountrySuggest] = useState(false)
  const [lookbackYears, setLookbackYears] = useState<number | null>(initialLookback)
  // Auto-open the filter panel when we arrive with filters already applied.
  const [showFilters, setShowFilters] = useState(
    phases.length + statuses.length + studyTypes.length + sponsorClasses.length > 0 || !!initialCountry
  )
  const [sortBy, setSortBy] = useState<'relevance' | 'enrollment' | 'startDate' | 'updated'>(initialSort)

  const fromYear = lookbackYears ? currentYear() - lookbackYears : null

  const activeFilterCount = phases.length + statuses.length + studyTypes.length +
    sponsorClasses.length + (country ? 1 : 0) + (lookbackYears ? 1 : 0)

  const sortParam = SORT_PARAM[sortBy]

  // Live search-as-you-type: debounce the condition only. Country is NOT committed
  // here — a half-typed name (e.g. "Ger") would drop results to zero — it commits
  // on Enter, a suggestion click, or Search instead.
  useEffect(() => {
    const t = setTimeout(() => setCondition(input.trim()), 400)
    return () => clearTimeout(t)
  }, [input])

  // Publish the full filter set so Historical & Geo reflect it automatically.
  useEffect(() => {
    if (condition.trim().length >= 2) {
      setSharedFilters({
        condition: condition.trim(),
        phases, statuses, studyTypes, sponsorClasses,
        country, fromYear,
      })
    }
  }, [condition, phases, statuses, studyTypes, sponsorClasses, country, fromYear, setSharedFilters])

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['studies', condition, phases, statuses, studyTypes, sponsorClasses, country, fromYear, sortBy],
    queryFn: () => api.searchStudies({
      condition,
      phases,
      status: statuses,
      studyTypes,
      sponsorClasses,
      country: country || undefined,
      fromYear,
      sort: sortParam,
      pageSize: 25,
    }),
    enabled: condition.trim().length >= 2,
  })

  const handleSearch = useCallback(() => {
    if (input.trim().length < 2) return
    // Explicit "run now" — commit immediately without waiting for the debounce.
    setCondition(input.trim())
    setCountry(countryInput.trim())
  }, [input, countryInput])

  const toggle = <T extends string>(set: T[], val: T, setFn: (v: T[]) => void) =>
    setFn(set.includes(val) ? set.filter(x => x !== val) : [...set, val])

  const clearAll = () => {
    setPhases([]); setStatuses([]); setStudyTypes([])
    setSponsorClasses([]); setCountry(''); setCountryInput(''); setLookbackYears(null)
  }

  const countrySuggestions = COMMON_COUNTRIES.filter(c =>
    c.toLowerCase().includes(countryInput.toLowerCase()) && countryInput.length > 0
  )

  const loading = isLoading || isFetching
  const hasQuery = condition.trim().length >= 2

  const observationalPhaseConflict =
    studyTypes.includes('OBSERVATIONAL') && phases.some(p => p !== 'NA')

  return (
    <div className="flex flex-col h-full bg-iq-bg">
      <TopBar title="Discovery Studio" subtitle="Search and explore clinical trials from ClinicalTrials.gov" />

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* Search hero */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass rounded-2xl p-6 border-iq-blue/30"
        >
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-iq-muted" />
              <input
                className="w-full bg-iq-bg border border-iq-border rounded-xl pl-10 pr-4 py-3 text-sm text-iq-text
                           placeholder-iq-muted focus:outline-none focus:border-iq-blue focus:ring-2 focus:ring-iq-blue/20 transition-all"
                placeholder="Enter indication, condition, or drug… e.g. AML, Breast Cancer, Pembrolizumab"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
              />
            </div>
            <button
              onClick={() => setShowFilters(f => !f)}
              className={clsx('btn-ghost flex items-center gap-2 px-3', showFilters && 'bg-iq-bg border-iq-blue text-iq-navy')}
            >
              <SlidersHorizontal className="w-4 h-4" />
              <span className="hidden sm:inline">Filters</span>
              {activeFilterCount > 0 && (
                <span className="bg-iq-blue text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                  {activeFilterCount}
                </span>
              )}
            </button>
            <button onClick={handleSearch} className="btn-primary flex items-center gap-2 px-5">
              <Search className="w-4 h-4" />
              Search
            </button>
          </div>

          {/* ── Expanded filter panel ── */}
          <AnimatePresence>
            {showFilters && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="pt-5 mt-4 border-t border-iq-border space-y-4">

                  {/* Row 1: Phase + Status */}
                  <div className="grid grid-cols-2 gap-5">
                    <FilterSection icon={<FlaskConical className="w-3 h-3" />} title="Phase">
                      <ChipGroup options={PHASES} selected={phases}
                        onToggle={v => toggle(phases, v, setPhases)} />
                    </FilterSection>
                    <FilterSection icon={<ArrowUpDown className="w-3 h-3" />} title="Status">
                      <ChipGroup options={STATUSES} selected={statuses}
                        onToggle={v => toggle(statuses, v, setStatuses)} />
                    </FilterSection>
                  </div>

                  {/* Row 2: Study Type + Sponsor Type */}
                  <div className="grid grid-cols-2 gap-5 pt-3 border-t border-iq-border">
                    <FilterSection icon={<Building2 className="w-3 h-3" />} title="Study Type">
                      <ChipGroup options={STUDY_TYPES} selected={studyTypes}
                        onToggle={v => toggle(studyTypes, v, setStudyTypes)} />
                    </FilterSection>
                    <FilterSection icon={<Briefcase className="w-3 h-3" />} title="Sponsor Type">
                      <ChipGroup options={SPONSOR_CLASSES} selected={sponsorClasses}
                        onToggle={v => toggle(sponsorClasses, v, setSponsorClasses)} />
                    </FilterSection>
                  </div>

                  {/* Observational + Phase warning */}
                  {observationalPhaseConflict && (
                    <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-orange-50 border border-orange-200">
                      <Info className="w-3.5 h-3.5 text-orange-600 flex-shrink-0 mt-0.5" />
                      <p className="text-[11px] text-orange-800">
                        Observational studies usually have <strong>no phase</strong> — combining them with a phase filter will exclude almost everything. Clear the phase chips (or keep only <span className="font-mono">N/A</span>) for observational results.
                      </p>
                    </div>
                  )}

                  {/* Row 3: Lookback + Country */}
                  <div className="grid grid-cols-2 gap-5 pt-3 border-t border-iq-border">
                    <FilterSection icon={<Clock className="w-3 h-3" />} title="Look-back Period">
                      <div className="flex flex-wrap gap-1.5">
                        {LOOKBACK_OPTIONS.map(opt => (
                          <button key={opt.label}
                            onClick={() => setLookbackYears(opt.years)}
                            className={clsx(
                              'chip text-[11px] px-2 py-0.5 transition-all',
                              lookbackYears === opt.years ? 'chip-active' : 'chip-idle',
                            )}>
                            {opt.label}
                          </button>
                        ))}
                      </div>
                      {lookbackYears && (
                        <p className="mt-1.5 text-[10px] text-iq-muted">
                          Trials started from Jan {currentYear() - lookbackYears}
                        </p>
                      )}
                    </FilterSection>

                    <FilterSection icon={<Globe className="w-3 h-3" />} title="Country">
                      <div className="relative">
                        <MapPin className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-iq-muted" />
                        <input
                          className="w-full bg-iq-bg border border-iq-border rounded-lg pl-7 pr-8 py-1.5 text-[12px] text-iq-text
                                     placeholder-iq-muted focus:outline-none focus:border-iq-blue transition-all"
                          placeholder="Filter by country…"
                          value={countryInput}
                          onChange={e => { setCountryInput(e.target.value); setShowCountrySuggest(true) }}
                          onKeyDown={e => { if (e.key === 'Enter') { setCountry(countryInput.trim()); setShowCountrySuggest(false) } }}
                          onBlur={() => setTimeout(() => setShowCountrySuggest(false), 150)}
                          onFocus={() => setShowCountrySuggest(true)}
                        />
                        {country && (
                          <button onClick={() => { setCountry(''); setCountryInput('') }}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-iq-muted hover:text-iq-navy">
                            <X className="w-3 h-3" />
                          </button>
                        )}
                        {showCountrySuggest && countrySuggestions.length > 0 && (
                          <div className="absolute top-full mt-1 left-0 right-0 z-50 glass rounded-lg overflow-hidden shadow-card-md border border-iq-border">
                            {countrySuggestions.slice(0, 6).map(c => (
                              <button key={c}
                                onMouseDown={() => { setCountry(c); setCountryInput(c); setShowCountrySuggest(false) }}
                                className="w-full text-left px-3 py-1.5 text-xs text-iq-text hover:bg-iq-bg transition-colors">
                                {c}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                      {country && (
                        <p className="mt-1.5 text-[10px] text-iq-blue font-medium">Filtering to: {country}</p>
                      )}
                    </FilterSection>
                  </div>

                  {/* Active filter pills + clear */}
                  {activeFilterCount > 0 && (
                    <div className="flex items-center gap-2 pt-2 flex-wrap">
                      <span className="text-[10px] text-iq-muted">Active:</span>
                      {phases.map(p => (
                        <span key={p} className="chip chip-active text-[10px] px-2 py-0.5 flex items-center gap-1">
                          {p.replace('_', ' ')}
                          <X className="w-2.5 h-2.5 cursor-pointer" onClick={() => toggle(phases, p, setPhases)} />
                        </span>
                      ))}
                      {statuses.map(s => (
                        <span key={s} className="chip chip-active text-[10px] px-2 py-0.5 flex items-center gap-1">
                          {s.replace(/_/g, ' ')}
                          <X className="w-2.5 h-2.5 cursor-pointer" onClick={() => toggle(statuses, s, setStatuses)} />
                        </span>
                      ))}
                      {studyTypes.map(t => (
                        <span key={t} className="chip chip-active text-[10px] px-2 py-0.5 flex items-center gap-1">
                          {t}
                          <X className="w-2.5 h-2.5 cursor-pointer" onClick={() => toggle(studyTypes, t, setStudyTypes)} />
                        </span>
                      ))}
                      {sponsorClasses.map(sc => (
                        <span key={sc} className="chip chip-active text-[10px] px-2 py-0.5 flex items-center gap-1">
                          {sc}
                          <X className="w-2.5 h-2.5 cursor-pointer" onClick={() => toggle(sponsorClasses, sc, setSponsorClasses)} />
                        </span>
                      ))}
                      {country && (
                        <span className="chip chip-active text-[10px] px-2 py-0.5 flex items-center gap-1">
                          {country}
                          <X className="w-2.5 h-2.5 cursor-pointer" onClick={() => { setCountry(''); setCountryInput('') }} />
                        </span>
                      )}
                      {lookbackYears && (
                        <span className="chip chip-active text-[10px] px-2 py-0.5 flex items-center gap-1">
                          Last {lookbackYears} yr
                          <X className="w-2.5 h-2.5 cursor-pointer" onClick={() => setLookbackYears(null)} />
                        </span>
                      )}
                      <button onClick={clearAll}
                        className="ml-auto text-[10px] text-iq-muted hover:text-iq-navy flex items-center gap-1 transition-colors">
                        <X className="w-3 h-3" /> Clear all
                      </button>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Quick searches */}
          {!hasQuery && (
            <div className="mt-4">
              <p className="text-[11px] text-iq-muted mb-2">Quick searches</p>
              <div className="flex flex-wrap gap-2">
                {QUICK_SEARCHES.map(q => (
                  <button key={q}
                    onClick={() => { setInput(q); setCondition(q) }}
                    className="chip chip-idle text-[11px] transition-all">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Smart search tip */}
          <div className="mt-4 flex items-center gap-2 p-3 rounded-lg bg-iq-blue/5 border border-iq-blue/20">
            <Sparkles className="w-3.5 h-3.5 text-iq-blue flex-shrink-0" />
            <p className="text-[11px] text-iq-muted">
              <span className="text-iq-navy font-semibold">Smart Search</span>
              {' '}— Search by condition, drug name, NCT ID, or sponsor. Use Filters to refine by phase, status, study type, sponsor, country, and look-back period.
            </p>
          </div>
        </motion.div>

        {/* Results */}
        {hasQuery && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-iq-border">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold text-iq-navy">Results</span>
                {!loading && data && (
                  <span className="text-xs text-iq-muted">
                    <AnimatedNumber value={data.totalCount} /> trials found for <em className="text-iq-blue">{condition}</em>
                    {activeFilterCount > 0 && (
                      <span className="text-iq-muted"> · {activeFilterCount} filter{activeFilterCount > 1 ? 's' : ''} active</span>
                    )}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5 text-xs text-iq-muted">
                <ArrowUpDown className="w-3.5 h-3.5" />
                <select
                  value={sortBy}
                  onChange={e => setSortBy(e.target.value as typeof sortBy)}
                  className="bg-white border border-iq-border rounded-md px-2 py-1.5 text-xs text-iq-text
                             focus:outline-none focus:border-iq-blue cursor-pointer"
                >
                  <option value="relevance">Relevance</option>
                  <option value="enrollment">Enrollment (high→low)</option>
                  <option value="startDate">Start date (newest)</option>
                  <option value="updated">Recently updated</option>
                </select>
              </div>
            </div>

            {isError && (
              <ErrorState error={error} onRetry={() => refetch()} />
            )}

            {!isError && (<>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-iq-border bg-iq-bg">
                    {['NCT ID', 'Title / Condition', 'Phase', 'Status', 'Type', 'Sponsor', 'N', 'Ctry', ''].map(h => (
                      <th key={h} className="px-3 py-2 text-left text-[10px] font-bold text-iq-muted uppercase tracking-wider whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading
                    ? Array.from({ length: 8 }).map((_, i) => (
                        <tr key={i}>
                          <td colSpan={9} className="p-0">
                            <SkeletonTableRow />
                          </td>
                        </tr>
                      ))
                    : data?.studies.map((s, i) => (
                        <StudyRow
                          key={s.nctId}
                          study={s}
                          index={i}
                          onClick={() => navigate(`/protocol/${s.nctId}`)}
                        />
                      ))
                  }
                </tbody>
              </table>
            </div>

            {!loading && data?.studies.length === 0 && (
              <div className="py-16 text-center">
                <Search className="w-8 h-8 mx-auto mb-3 text-iq-border" />
                <p className="text-sm text-iq-muted">No trials found for <strong className="text-iq-text">{condition}</strong></p>
                <p className="text-xs mt-1 text-iq-muted">Try a broader search term or remove filters</p>
              </div>
            )}

            {!loading && data && data.studies.length > 0 && (
              <div className="px-5 py-3 border-t border-iq-border bg-iq-bg flex items-center gap-6 text-[11px] text-iq-muted">
                <span className="flex items-center gap-1.5"><Users className="w-3 h-3" />
                  Showing {data.studies.length} of {data.totalCount.toLocaleString()}
                </span>
                <span className="flex items-center gap-1.5"><Building2 className="w-3 h-3" />
                  {[...new Set(data.studies.map(s => s.sponsor.class))].join(' · ')}
                </span>
                <span className="flex items-center gap-1.5"><MapPin className="w-3 h-3" />
                  {[...new Set(data.studies.flatMap(s => Object.keys(s.countries)))].length} countries
                </span>
              </div>
            )}
            </>
            )}
          </motion.div>
        )}

        {!hasQuery && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { delay: 0.3 } }}
            className="text-center py-20"
          >
            <div className="w-16 h-16 rounded-2xl bg-iq-blue/10 flex items-center justify-center mx-auto mb-4 border border-iq-blue/20">
              <Search className="w-7 h-7 text-iq-blue" />
            </div>
            <h3 className="text-lg font-semibold text-iq-navy mb-2">Search Clinical Trials</h3>
            <p className="text-sm text-iq-muted max-w-xs mx-auto">
              Enter a condition, indication, drug name, or NCT ID to explore global trial data
            </p>
          </motion.div>
        )}
      </div>
    </div>
  )
}
