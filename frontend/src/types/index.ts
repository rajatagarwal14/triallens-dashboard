export interface Study {
  nctId: string
  title: string
  officialTitle?: string
  status: string
  phases: string[]
  studyType: string
  summary: string
  conditions: string[]
  keywords: string[]
  interventions: { type: string; name: string }[]
  sponsor: { name: string; class: string }
  enrollment: { count: number | null; type: string } | null
  startDate: string | null
  completionDate: string | null
  eligibility: {
    criteria: string
    healthyVolunteers: boolean
    sex: string
    minimumAge: string
    maximumAge: string
  }
  countries: Record<string, number>
  sites: Site[]
  countryCount: number
  siteCount: number
}

export interface Site {
  nctId?: string
  facility: string
  city: string
  country: string
  status?: string
  lat: number
  lon: number
}

export interface SearchResult {
  studies: Study[]
  totalCount: number
  nextPageToken?: string
}

export interface Coverage {
  analyzed: number
  total: number
  isComplete: boolean
}

export interface LandscapeData {
  totalCount: number
  sampleSize: number
  coverage: Coverage
  phaseCounts: Record<string, number>
  statusCounts: Record<string, number>
  sponsorClassCounts: Record<string, number>
  countryCounts: Record<string, number>
  yearCounts: Record<string, number>
  enrollmentByYear: Record<string, number>
  yearByPhase: Record<string, Record<string, number>>
  yearBySponsor: Record<string, Record<string, number>>
  avgEnrollment: number
}

export interface GeoCountry {
  country: string
  trialCount: number
  siteCount: number
  competingEnrollment?: number
  prevalence?: number | null
  competitionIntensity?: number | null
  sites: Site[]
}

export interface EligibilityExtracted {
  ageRange: { min: number | null; max: number | null }
  biomarkers: string[]
  biomarkersExcluded: string[]
  diseaseStage: string[]
  priorTreatment: string[]
  complexityScore: number
  inclusionText: string
  exclusionText: string
}

export interface SimilarStudy {
  study: Study
  score: number
  sharedConditions: string[]
  sharedKeywords: string[]
}

export interface SponsorRow {
  sponsor: string
  class: string
  trials: number
  phases: Record<string, number>
  statuses: Record<string, number>
  enrollment: number
  lateStage: number
}

export interface Readout {
  nctId: string
  title: string
  sponsor: string
  sponsorClass: string
  phase: string
  status: string
  enrollment: number | null
  primaryCompletionDate: string | null
  primaryCompletionType: string | null
  countryCount: number
}

export interface CompetitionData {
  coverage: Coverage
  totalCount: number
  leaderboard: SponsorRow[]
  timeline: { period: string; count: number }[]
  readouts: Readout[]
  readoutCount: number
}

export interface AlertTrial {
  nctId: string
  title: string
  sponsor: string
  phase: string
  status: string
  firstPostDate: string | null
  countryCount: number
}

export interface AlertData {
  since: string
  days: number
  count: number
  trials: AlertTrial[]
}

export interface SiteRow {
  facility: string
  trials: number
  enrollment: number
  avgEnrollment: number
  country: string
  city: string
  phases: Record<string, number>
  recruiting: number
  enrollRate: number
  sampleNct: string
}

export interface InvestigatorRow {
  name: string
  trials: number
  enrollment: number
  avgEnrollment: number
  affiliation: string
  focus: string[]
  phases: Record<string, number>
  recruiting: number
  enrollRate: number
  sampleNct: string
}

export interface SitesData {
  coverage: Coverage
  sites: SiteRow[]
  investigators: InvestigatorRow[]
  siteUniverse: number
  investigatorUniverse: number
}

export interface MarketRestrictiveness {
  condition: string
  peerCount: number
  percentile: number
  marketMedian: number
  marketAvg: number
  myScore: number
}

export interface Insight { kind: string; title: string; detail: string }

export interface ResearchData {
  coverage: Coverage
  insights: Insight[]
  readoutForecast: {
    byYear: Array<{ year: number; total: number } & Record<string, number>>
    phases: string[]
    phaseLabels: Record<string, string>
    upcomingTotal: number
    upcomingPhase3: number
  }
  timeToCompletion: { phase: string; medianMonths: number; n: number }[]
  discontinuation: { phase: string; rate: number; dropped: number; total: number }[]
  enrollmentBenchmarks: { phase: string; median: number; n: number }[]
  enrollmentRate: { phase: string; perSiteMonth: number; n: number }[]
  countryActivity: {
    top: { country: string; trials: number }[]
    top3Share: number
    totalCountries: number
  }
}

export interface CohortGroup {
  key: string
  label: string
  definition: string
  trialCount: number
  enrollPacePerSiteMonth: number | null
  enrollPaceN: number
  medianDurationMonths: number | null
  medianEnrollment: number | null
  discontinuationRate: number
  discontinued: number
  nctSample: string[]
}

export interface CohortAxis {
  key: string
  label: string
  groupCount: number
  applicable: boolean
}

export interface CohortData {
  coverage: Coverage
  query: { primary: string | null; qualifiers: string[] }
  axis: string
  suggestedAxis: string
  availableAxes: CohortAxis[]
  groups: CohortGroup[]
}

export type StatusFilter =
  | 'RECRUITING'
  | 'NOT_YET_RECRUITING'
  | 'ACTIVE_NOT_RECRUITING'
  | 'ENROLLING_BY_INVITATION'
  | 'COMPLETED'
  | 'TERMINATED'
  | 'WITHDRAWN'
  | 'SUSPENDED'
  | 'UNKNOWN'
  | 'NO_LONGER_AVAILABLE'
  | 'APPROVED_FOR_MARKETING'
  | 'AVAILABLE'
  | 'TEMPORARILY_NOT_AVAILABLE'
  | 'WITHHELD'

export type PhaseFilter = 'EARLY_PHASE1' | 'PHASE1' | 'PHASE2' | 'PHASE3' | 'PHASE4' | 'NA'

export type StudyType = 'INTERVENTIONAL' | 'OBSERVATIONAL' | 'EXPANDED_ACCESS'

export type SponsorClass = 'INDUSTRY' | 'NIH' | 'FED' | 'OTHER' | 'INDIV' | 'NETWORK'

export interface SearchFilters {
  condition: string
  status: StatusFilter[]
  phases: PhaseFilter[]
  studyTypes: StudyType[]
  sponsorClasses: SponsorClass[]
  country: string
  fromYear: number | null
  sort?: string
  pageSize: number
  pageToken?: string
}
