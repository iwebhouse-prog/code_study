import { QueryClient } from '@tanstack/react-query'

// Data counts as fresh for 30 seconds; after that it is shown from cache and
// refreshed in the background (stale-while-revalidate, research.md section 10).
export const STALE_TIME_MS = 30_000
export const MAX_QUERY_RETRIES = 2

/** HTTP status of a failed request, or undefined for network errors. */
export function getHttpStatus(error: unknown): number | undefined {
  if (typeof error !== 'object' || error === null) return undefined
  const { response, status } = error as {
    response?: { status?: unknown }
    status?: unknown
  }
  const value = response?.status ?? status
  return typeof value === 'number' ? value : undefined
}

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  const status = getHttpStatus(error)
  // 4xx means the request itself is wrong (or not allowed); asking again gives
  // the same answer, and retrying 429 would only add to the rate limit.
  if (status !== undefined && status >= 400 && status < 500) return false
  return failureCount < MAX_QUERY_RETRIES
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: STALE_TIME_MS,
        retry: shouldRetryQuery,
      },
      mutations: {
        // A retried POST could create the same project or task twice.
        retry: false,
      },
    },
  })
}
