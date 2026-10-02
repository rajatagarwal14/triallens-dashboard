import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Layers, Loader2, RefreshCw, DownloadCloud } from 'lucide-react'
import { clsx } from 'clsx'
import { api } from '@/api/client'
import { useSharedSearch, filterParams } from '@/context/SearchContext'
import type { Coverage } from '@/types'

const ANALYTIC_KEYS = new Set(['landscape', 'geo', 'competition', 'research', 'sites', 'cohorts'])
const BASE = 'inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full border'

function when(iso?: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

/**
 * Honest data-coverage label:
 *  • retrieving → "Retrieved 3,000 of 16,873 · partial" with a progress bar
 *  • complete   → "Complete · 16,873 trials · retrieved <time>" (+ refresh)
 *  • capped     → stopped at the safety cap, with an explicit "Retrieve all" button
 *  • paused / error → says so, keeps what was retrieved, retries automatically
 */
export function CoverageBadge({ coverage, className, params }: {
  coverage?: Coverage
  className?: string
  /** Query params that identify the dataset (defaults to the shared search filters). */
  params?: Record<string, string | number | undefined>
}) {
  const { filters } = useSharedSearch()
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  if (!coverage) return null

  const { analyzed, total, isComplete, state, capped, refreshing, error } = coverage
  const q = params ?? filterParams(filters)
  const act = async (fn: (p: Record<string, string | number | undefined>) => Promise<unknown>) => {
    setBusy(true)
    try { await fn(q) } finally {
      setBusy(false)
      // re-pull the analytics only (not Discovery search / prevalence) for the new dataset version
      qc.invalidateQueries({ predicate: q => ANALYTIC_KEYS.has(String(q.queryKey[0])) })
    }
  }
  const pct = total > 0 ? Math.min(100, Math.round((analyzed / total) * 100)) : 0

  if (isComplete) {
    return (
      <span className={clsx(BASE, 'bg-green-50 text-green-700 border-green-200', className)}
        title={`Every matching study was retrieved from ClinicalTrials.gov${coverage.completedAt ? ` (completed ${when(coverage.completedAt)})` : ''} and stored locally; charts use all of them.`}>
        <CheckCircle2 className="w-2.5 h-2.5" />
        Complete · {total.toLocaleString()} trials{coverage.retrievedAt ? ` · retrieved ${when(coverage.retrievedAt)}` : ''}
        {refreshing
          ? <Loader2 className="w-2.5 h-2.5 animate-spin" />
          : <button disabled={busy} onClick={() => act(api.datasetRefresh)} title="Check for new and changed trials"
              className="ml-0.5 hover:text-green-900"><RefreshCw className="w-2.5 h-2.5" /></button>}
      </span>
    )
  }

  if (capped || state === 'capped') {
    return (
      <span className={clsx(BASE, 'bg-orange-50 text-orange-700 border-orange-200', className)}
        title={coverage.note ?? 'Retrieval stopped at the safety limit to protect memory.'}>
        <Layers className="w-2.5 h-2.5" />
        Retrieved {analyzed.toLocaleString()} of {total.toLocaleString()} · partial (safety limit)
        <button disabled={busy} onClick={() => act(api.datasetContinue)}
          className="ml-1 inline-flex items-center gap-1 underline font-semibold">
          <DownloadCloud className="w-2.5 h-2.5" /> Retrieve all
        </button>
      </span>
    )
  }

  if (state === 'paused' || state === 'error') {
    return (
      <span className={clsx(BASE, 'bg-red-50 text-red-700 border-red-200', className)}
        title={error ?? 'Retrieval interrupted'}>
        <AlertTriangle className="w-2.5 h-2.5" />
        {analyzed.toLocaleString()} of {total.toLocaleString()} retrieved · partial — {error ?? 'retrying'}
        <Loader2 className="w-2.5 h-2.5 animate-spin" />
      </span>
    )
  }

  // retrieving
  return (
    <span className={clsx(BASE, 'bg-orange-50 text-orange-700 border-orange-200', className)}
      title="Charts update as pages arrive and are final once every study is retrieved.">
      <Loader2 className="w-2.5 h-2.5 animate-spin" />
      Retrieved {analyzed.toLocaleString()} of {total.toLocaleString()} · partial
      <span className="w-14 h-1 rounded bg-orange-200 overflow-hidden">
        <span className="block h-full bg-orange-500" style={{ width: `${pct}%` }} />
      </span>
    </span>
  )
}
