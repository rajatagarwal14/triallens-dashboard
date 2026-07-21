import { AlertTriangle, RotateCcw } from 'lucide-react'
import { motion } from 'framer-motion'

export function ErrorState({
  error, onRetry, compact = false,
}: {
  error: unknown
  onRetry?: () => void
  compact?: boolean
}) {
  const message = error instanceof Error ? error.message : 'Something went wrong fetching data.'

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className={compact
        ? 'flex items-center gap-3 px-4 py-3 rounded-lg bg-red-50 border border-red-200'
        : 'flex flex-col items-center justify-center text-center py-16 px-6'}
    >
      <div className={compact
        ? 'w-7 h-7 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0'
        : 'w-12 h-12 rounded-xl bg-red-100 flex items-center justify-center mb-4 border border-red-200'}>
        <AlertTriangle className={compact ? 'w-3.5 h-3.5 text-red-600' : 'w-5 h-5 text-red-600'} />
      </div>
      <div className={compact ? 'flex-1 min-w-0' : ''}>
        {!compact && <h3 className="text-sm font-semibold text-iq-text mb-1">Couldn't load data</h3>}
        <p className={compact ? 'text-xs text-iq-muted' : 'text-xs text-iq-muted max-w-sm'}>{message}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry}
          className={compact
            ? 'btn-ghost text-xs flex items-center gap-1.5 py-1.5 flex-shrink-0'
            : 'btn-ghost text-xs flex items-center gap-1.5 py-1.5 mt-4'}>
          <RotateCcw className="w-3.5 h-3.5" /> Retry
        </button>
      )}
    </motion.div>
  )
}
