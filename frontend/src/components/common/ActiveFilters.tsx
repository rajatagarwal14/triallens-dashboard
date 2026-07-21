import { SlidersHorizontal, X } from 'lucide-react'
import { useSharedSearch } from '@/context/SearchContext'

const PHASE_LABEL: Record<string, string> = {
  EARLY_PHASE1: 'Early I', PHASE1: 'Phase I', PHASE2: 'Phase II',
  PHASE3: 'Phase III', PHASE4: 'Phase IV', NA: 'N/A',
}
const STATUS_LABEL: Record<string, string> = {
  RECRUITING: 'Recruiting', NOT_YET_RECRUITING: 'Not Yet Recruiting',
  ACTIVE_NOT_RECRUITING: 'Active', ENROLLING_BY_INVITATION: 'By Invitation',
  COMPLETED: 'Completed', TERMINATED: 'Terminated', WITHDRAWN: 'Withdrawn', SUSPENDED: 'Suspended',
}
const TYPE_LABEL: Record<string, string> = {
  INTERVENTIONAL: 'Interventional', OBSERVATIONAL: 'Observational', EXPANDED_ACCESS: 'Expanded Access',
}

/**
 * Read-only strip showing the filters currently shared from Discovery, so the
 * user can see (and clear) what's narrowing the Historical / Geo view.
 */
export function ActiveFilters() {
  const { filters, setFilters } = useSharedSearch()
  const chips: string[] = [
    ...filters.phases.map(p => PHASE_LABEL[p] ?? p),
    ...filters.statuses.map(s => STATUS_LABEL[s] ?? s),
    ...filters.studyTypes.map(t => TYPE_LABEL[t] ?? t),
    ...filters.sponsorClasses.map(s => s.charAt(0) + s.slice(1).toLowerCase()),
    ...(filters.country ? [filters.country] : []),
    ...(filters.fromYear ? [`Since ${filters.fromYear}`] : []),
  ]
  if (chips.length === 0) return null

  const clear = () => setFilters({
    phases: [], statuses: [], studyTypes: [], sponsorClasses: [], country: '', fromYear: null,
  })

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="flex items-center gap-1 text-[10px] text-iq-muted font-medium">
        <SlidersHorizontal className="w-3 h-3" /> Filters from Discovery:
      </span>
      {chips.map(c => (
        <span key={c} className="text-[10px] bg-iq-blue/10 text-iq-navy border border-iq-blue/20 px-2 py-0.5 rounded-full">
          {c}
        </span>
      ))}
      <button onClick={clear}
        className="text-[10px] text-iq-muted hover:text-iq-navy flex items-center gap-0.5 transition-colors">
        <X className="w-3 h-3" /> clear
      </button>
    </div>
  )
}
