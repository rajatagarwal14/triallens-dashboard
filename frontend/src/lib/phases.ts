// One definition of how a registry phase key is shown, used by every page.
// Keys are CT.gov values, or "/"-joined for a trial registered in two phases
// (e.g. "PHASE2/PHASE3"), which the backend counts once, as its own category.
const ROMAN: Record<string, string> = {
  EARLY_PHASE1: 'Early I', PHASE1: 'I', PHASE2: 'II', PHASE3: 'III', PHASE4: 'IV',
}

export const PHASE_COLORS: Record<string, string> = {
  EARLY_PHASE1: '#7FA9C3',
  PHASE1: '#005487',
  'PHASE1/PHASE2': '#0072B0',
  PHASE2: '#00A3E0',
  'PHASE2/PHASE3': '#3DB5A0',
  PHASE3: '#6CC04A',
  PHASE4: '#FE8A12',
  NA: '#B0BEC5',
}

export function phaseLabel(key: string): string {
  if (key === 'NA' || key === 'N/A') return 'N/A'
  if (key === 'EARLY_PHASE1') return 'Early Phase I'
  const parts = key.split('/')
  if (parts.every(p => ROMAN[p])) return 'Phase ' + parts.map(p => ROMAN[p]).join('/')
  return key
}

export const phaseColor = (key: string) => PHASE_COLORS[key] ?? '#B0BEC5'
