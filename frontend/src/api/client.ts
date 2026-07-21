import type {
  SearchResult, Study, LandscapeData, GeoCountry, Coverage,
  EligibilityExtracted, SimilarStudy, SearchFilters,
  CompetitionData, ResearchData, AlertData, SitesData, MarketRestrictiveness,
  CohortData,
} from '@/types'

const BASE = '/api'

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
    })
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    // Surface the backend's human-readable message when present
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.error) message = body.error
    } catch { /* non-JSON error body — keep status text */ }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

export const api = {
  searchStudies: (filters: Partial<SearchFilters>): Promise<SearchResult> =>
    get('/studies/', {
      condition: filters.condition,
      status: filters.status?.join(','),
      phases: filters.phases?.join(','),
      studyTypes: filters.studyTypes?.join(','),
      sponsorClasses: filters.sponsorClasses?.join(','),
      country: filters.country,
      fromYear: filters.fromYear ?? undefined,
      sort: filters.sort,
      pageSize: filters.pageSize ?? 25,
      pageToken: filters.pageToken,
    }),

  getStudy: (nctId: string): Promise<Study> =>
    get(`/studies/${nctId}`),

  getLandscape: (params: Record<string, string | number | undefined>): Promise<LandscapeData> =>
    get('/landscape/', params),

  getGeo: (params: Record<string, string | number | undefined>): Promise<{ countries: GeoCountry[]; coverage: Coverage; hasPrevalence?: boolean }> =>
    get('/landscape/geo', params),

  getSites: (params: Record<string, string | number | undefined>): Promise<SitesData> =>
    get('/sites/', params),

  getSimilar: (nctId: string): Promise<{ target: Study; similar: SimilarStudy[] }> =>
    get(`/similarity/${nctId}`),

  getEligibility: (nctId: string): Promise<{ extracted: EligibilityExtracted; study: Study; market: MarketRestrictiveness | null }> =>
    get(`/landscape/eligibility/${nctId}`),

  getCompetition: (params: Record<string, string | number | undefined>): Promise<CompetitionData> =>
    get('/competition/', params),

  getResearch: (params: Record<string, string | number | undefined>): Promise<ResearchData> =>
    get('/research/', params),

  getCohorts: (params: Record<string, string | number | undefined>): Promise<CohortData> =>
    get('/cohorts/', params),

  getAlerts: (params: Record<string, string | number | undefined>): Promise<AlertData> =>
    get('/alerts/', params),

  getPrevalence: (condition: string): Promise<{
    condition: string
    found: boolean
    method?: 'curated' | 'modeled' | 'none'
    modeled?: boolean
    countries: Record<string, { prevalence: number; source: string; confidence: string; note: string; method?: string }>
    supported?: string[]
    note: string
  }> => get('/landscape/prevalence', { condition }),
}
