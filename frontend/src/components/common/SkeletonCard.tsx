import { clsx } from 'clsx'

function Shimmer({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <div style={style} className={clsx(
      'rounded bg-iq-border animate-pulse relative overflow-hidden',
      className,
    )}>
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent" />
    </div>
  )
}

export function SkeletonStatCard() {
  return (
    <div className="glass rounded-xl p-5 space-y-3">
      <div className="flex justify-between">
        <Shimmer className="h-3 w-24" />
        <Shimmer className="h-6 w-6 rounded-md" />
      </div>
      <Shimmer className="h-8 w-32" />
      <Shimmer className="h-3 w-20" />
    </div>
  )
}

export function SkeletonTableRow() {
  return (
    <div className="flex gap-4 px-4 py-3 border-b border-iq-border">
      <Shimmer className="h-4 w-28" />
      <Shimmer className="h-4 flex-1" />
      <Shimmer className="h-4 w-16" />
      <Shimmer className="h-4 w-20" />
      <Shimmer className="h-4 w-14" />
    </div>
  )
}

export function SkeletonChart({ height = 200 }: { height?: number }) {
  return <Shimmer className="rounded-xl w-full" style={{ height }} />
}
