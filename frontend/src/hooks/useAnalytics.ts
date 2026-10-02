import { useQuery, type QueryKey } from '@tanstack/react-query'
import type { Coverage } from '@/types'

/**
 * useQuery for the analytics endpoints. The backend retrieves the full result set in the
 * background; while that is running the response is partial, so keep re-fetching (cheap —
 * the server memoises per dataset version) until it is complete.
 */
export function useAnalytics<T extends { coverage?: Coverage }>(key: QueryKey, fn: () => Promise<T>, enabled = true) {
  return useQuery({
    queryKey: key,
    queryFn: fn,
    enabled,
    refetchInterval: q => {
      const c = q.state.data?.coverage
      if (!c) return false
      if (c.state === 'retrieving' || c.state === 'new' || c.refreshing) return 3000
      if (c.state === 'paused' || (c.state === 'error' && !c.isComplete)) return 10000  // keep trying
      return false
    },
    refetchIntervalInBackground: false,
  })
}
