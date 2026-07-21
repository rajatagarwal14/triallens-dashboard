import { CheckCircle2, Layers } from 'lucide-react'
import { clsx } from 'clsx'
import type { Coverage } from '@/types'

export function CoverageBadge({ coverage, className }: { coverage?: Coverage; className?: string }) {
  if (!coverage) return null
  const { analyzed, total, isComplete } = coverage

  if (isComplete) {
    return (
      <span className={clsx(
        'inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full',
        'bg-green-50 text-green-700 border border-green-200',
        className,
      )}>
        <CheckCircle2 className="w-2.5 h-2.5" />
        Full dataset · {total.toLocaleString()} trials
      </span>
    )
  }

  return (
    <span className={clsx(
      'inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full',
      'bg-orange-50 text-orange-700 border border-orange-200',
      className,
    )}
      title={`These charts are computed from the first ${analyzed.toLocaleString()} of ${total.toLocaleString()} trials, ordered by ClinicalTrials.gov relevance. Narrow your search to get full coverage.`}
    >
      <Layers className="w-2.5 h-2.5" />
      Based on {analyzed.toLocaleString()} of {total.toLocaleString()} · top by relevance
    </span>
  )
}
