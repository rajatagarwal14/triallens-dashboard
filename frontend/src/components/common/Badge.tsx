import { clsx } from 'clsx'

const STATUS_MAP: Record<string, string> = {
  RECRUITING:              'status-recruiting',
  NOT_YET_RECRUITING:      'status-enrolling',
  ACTIVE_NOT_RECRUITING:   'status-active',
  COMPLETED:               'status-completed',
  TERMINATED:              'status-terminated',
  WITHDRAWN:               'status-withdrawn',
  SUSPENDED:               'status-suspended',
  ENROLLING_BY_INVITATION: 'status-enrolling',
  UNKNOWN:                 'status-unknown',
  NO_LONGER_AVAILABLE:     'status-nla',
  APPROVED_FOR_MARKETING:  'status-approved',
  AVAILABLE:               'status-available',
  TEMPORARILY_NOT_AVAILABLE: 'status-tempna',
  WITHHELD:                'status-withheld',
}

const PHASE_MAP: Record<string, string> = {
  PHASE1:       'phase-1',
  EARLY_PHASE1: 'phase-1',
  PHASE2:       'phase-2',
  PHASE3:       'phase-3',
  PHASE4:       'phase-4',
}

const STATUS_LABELS: Record<string, string> = {
  RECRUITING:              'Recruiting',
  NOT_YET_RECRUITING:      'Not Yet Recruiting',
  ACTIVE_NOT_RECRUITING:   'Active',
  COMPLETED:               'Completed',
  TERMINATED:              'Terminated',
  WITHDRAWN:               'Withdrawn',
  SUSPENDED:               'Suspended',
  ENROLLING_BY_INVITATION: 'By Invitation',
  UNKNOWN:                 'Unknown',
  NO_LONGER_AVAILABLE:     'No Longer Available',
  APPROVED_FOR_MARKETING:  'Approved for Marketing',
  AVAILABLE:               'Available',
  TEMPORARILY_NOT_AVAILABLE: 'Temp. Unavailable',
  WITHHELD:                'Withheld',
}

const PHASE_LABELS: Record<string, string> = {
  PHASE1: 'Phase I', EARLY_PHASE1: 'Early Phase I',
  PHASE2: 'Phase II', PHASE3: 'Phase III', PHASE4: 'Phase IV', NA: 'N/A',
}

interface Props {
  value: string
  type: 'status' | 'phase'
  size?: 'sm' | 'md'
}

export function Badge({ value, type, size = 'sm' }: Props) {
  const cls = type === 'status'
    ? STATUS_MAP[value] ?? 'status-default'
    : PHASE_MAP[value] ?? 'status-default'

  const label = type === 'status'
    ? (STATUS_LABELS[value] ?? value)
    : (PHASE_LABELS[value] ?? value)

  return (
    <span className={clsx(
      'inline-flex items-center rounded-full font-medium whitespace-nowrap',
      size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs',
      cls,
    )}>
      {type === 'status' && (
        <span className={clsx('w-1.5 h-1.5 rounded-full mr-1.5', {
          'bg-green-500 animate-pulse-slow': value === 'RECRUITING',
          'bg-cyan-500':   value === 'NOT_YET_RECRUITING',
          'bg-blue-500':   value === 'ACTIVE_NOT_RECRUITING',
          'bg-slate-400':  value === 'COMPLETED',
          'bg-red-500':    value === 'TERMINATED',
          'bg-orange-500': value === 'WITHDRAWN',
          'bg-yellow-500': value === 'SUSPENDED',
          'bg-sky-500':    value === 'ENROLLING_BY_INVITATION',
          'bg-gray-300':   value === 'UNKNOWN',
          'bg-rose-500':   value === 'NO_LONGER_AVAILABLE',
          'bg-teal-500':   value === 'APPROVED_FOR_MARKETING',
          'bg-lime-500':   value === 'AVAILABLE',
          'bg-yellow-600': value === 'TEMPORARILY_NOT_AVAILABLE',
          'bg-stone-400':  value === 'WITHHELD',
          'bg-gray-400':   !STATUS_MAP[value],
        })} />
      )}
      {label}
    </span>
  )
}
