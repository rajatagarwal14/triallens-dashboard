import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react'
import type { PhaseFilter, StatusFilter, StudyType, SponsorClass } from '@/types'

/**
 * Shared search + filter state so whatever the user sets on Discovery is
 * automatically reflected on Historical and Geo (and vice-versa). Pages remount
 * on route change and read this on mount; whichever page the user edits writes
 * the latest values here.
 */
export interface SharedFilters {
  condition: string
  phases: PhaseFilter[]
  statuses: StatusFilter[]
  studyTypes: StudyType[]
  sponsorClasses: SponsorClass[]
  country: string
  fromYear: number | null
}

export const EMPTY_FILTERS: SharedFilters = {
  condition: 'Cancer',
  phases: [], statuses: [], studyTypes: [], sponsorClasses: [],
  country: '', fromYear: null,
}

interface SearchCtx {
  filters: SharedFilters
  setFilters: (patch: Partial<SharedFilters>) => void
}

const Ctx = createContext<SearchCtx>({ filters: EMPTY_FILTERS, setFilters: () => {} })

export function SearchProvider({ children }: { children: ReactNode }) {
  const [filters, setFiltersState] = useState<SharedFilters>(EMPTY_FILTERS)
  // Stable identity so consumers can safely depend on it in effects without loops.
  const setFilters = useCallback((patch: Partial<SharedFilters>) => {
    setFiltersState(prev => {
      const next = { ...prev, ...patch }
      // No-op if nothing actually changed — prevents redundant re-renders.
      const same = (Object.keys(next) as (keyof SharedFilters)[]).every(k =>
        Array.isArray(next[k]) && Array.isArray(prev[k])
          ? JSON.stringify(next[k]) === JSON.stringify(prev[k])
          : next[k] === prev[k]
      )
      return same ? prev : next
    })
  }, [])
  const value = useMemo(() => ({ filters, setFilters }), [filters, setFilters])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useSharedSearch = () => useContext(Ctx)

// Serialize shared filters into query params for the landscape/geo API calls.
export function filterParams(f: SharedFilters) {
  return {
    condition: f.condition,
    status: f.statuses.length ? f.statuses.join(',') : undefined,
    phases: f.phases.length ? f.phases.join(',') : undefined,
    studyTypes: f.studyTypes.length ? f.studyTypes.join(',') : undefined,
    sponsorClasses: f.sponsorClasses.length ? f.sponsorClasses.join(',') : undefined,
    country: f.country || undefined,
    fromYear: f.fromYear ?? undefined,
  }
}
