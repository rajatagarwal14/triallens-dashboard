import type {
  SearchResult, Study, LandscapeData, GeoCountry, Coverage,
  EligibilityExtracted, SimilarStudy, SearchFilters,
  CompetitionData, ResearchData, AlertData, SitesData, MarketRestrictiveness,
  CohortData, PrevalenceResponse,
} from '@/types'

const BASE = '/api'

type Params = Record<string, string | number | boolean | undefined>

async function send<T>(method: 'GET' | 'POST', path: string, params?: Params): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
    })
  }
  let res: Response
  try {
    res = await fetch(url.toString(), { method })
  } catch {
    throw new Error('Cannot reach the TrialLens backend. Is it running? (start.bat / start.sh)')
  }
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

const get = <T,>(path: string, params?: Params) => send<T>('GET', path, params)
const post = <T,>(path: string, params?: Params) => send<T>('POST', path, params)

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

  getPrevalence: (condition: string): Promise<PrevalenceResponse> =>
    get('/landscape/prevalence', { condition }),

  // Retrieval progress for the dataset behind the current filters.
  datasetStatus: (params: Params): Promise<Coverage> => get('/datasets/status', params),
  datasetContinue: (params: Params): Promise<Coverage> => post('/datasets/continue', params),
  datasetRefresh: (params: Params): Promise<Coverage> => post('/datasets/refresh', params),
}
