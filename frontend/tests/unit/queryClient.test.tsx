import { QueryClientProvider, useQuery } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import {
  MAX_QUERY_RETRIES,
  STALE_TIME_MS,
  createQueryClient,
  getHttpStatus,
  shouldRetryQuery,
} from '../../src/lib/queryClient'

describe('getHttpStatus', () => {
  it('reads an axios-style error (error.response.status)', () => {
    expect(getHttpStatus({ response: { status: 404 } })).toBe(404)
  })

  it('reads an error with a status field', () => {
    expect(getHttpStatus({ status: 503 })).toBe(503)
  })

  it('returns undefined when there is no HTTP status (network error)', () => {
    expect(getHttpStatus(new Error('Network Error'))).toBeUndefined()
    expect(getHttpStatus(null)).toBeUndefined()
    expect(getHttpStatus('oops')).toBeUndefined()
  })
})

describe('shouldRetryQuery', () => {
  it.each([400, 401, 403, 404, 409, 422, 429])(
    'does not retry client error %i (asking again gives the same answer)',
    (status) => {
      expect(shouldRetryQuery(0, { response: { status } })).toBe(false)
    },
  )

  it.each([500, 502, 503])('retries server error %i', (status) => {
    expect(shouldRetryQuery(0, { response: { status } })).toBe(true)
  })

  it('retries network errors', () => {
    expect(shouldRetryQuery(0, new Error('Network Error'))).toBe(true)
  })

  it(`stops after ${MAX_QUERY_RETRIES} retries`, () => {
    const error = { response: { status: 503 } }
    expect(shouldRetryQuery(MAX_QUERY_RETRIES - 1, error)).toBe(true)
    expect(shouldRetryQuery(MAX_QUERY_RETRIES, error)).toBe(false)
  })
})

describe('createQueryClient', () => {
  it('uses the shared defaults', () => {
    const defaults = createQueryClient().getDefaultOptions()
    expect(defaults.queries?.staleTime).toBe(STALE_TIME_MS)
    expect(defaults.queries?.retry).toBe(shouldRetryQuery)
    // Saving twice could create duplicates, so mutations never retry.
    expect(defaults.mutations?.retry).toBe(false)
  })

  it('keeps data fresh for 30 seconds', () => {
    expect(STALE_TIME_MS).toBe(30_000)
  })

  it('returns a new client each time', () => {
    expect(createQueryClient()).not.toBe(createQueryClient())
  })
})

function Probe({ fetcher }: { fetcher: () => Promise<string> }) {
  const query = useQuery({ queryKey: ['probe'], queryFn: fetcher, retryDelay: 0 })
  if (query.isPending) return <p>loading</p>
  if (query.isError) return <p>failed</p>
  return <p>{query.data}</p>
}

function renderProbe(fetcher: () => Promise<string>) {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <Probe fetcher={fetcher} />
    </QueryClientProvider>,
  )
}

describe('queries with the shared client', () => {
  it('a 404 fails after one request', async () => {
    const fetcher = vi.fn().mockRejectedValue({ response: { status: 404 } })
    renderProbe(fetcher)
    expect(await screen.findByText('failed')).toBeInTheDocument()
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('a temporary 503 is retried until it succeeds', async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce({ response: { status: 503 } })
      .mockResolvedValueOnce('ok')
    renderProbe(fetcher)
    expect(await screen.findByText('ok')).toBeInTheDocument()
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('a server that keeps failing is tried 1 + 2 times', async () => {
    const fetcher = vi.fn().mockRejectedValue({ response: { status: 500 } })
    renderProbe(fetcher)
    expect(await screen.findByText('failed')).toBeInTheDocument()
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1 + MAX_QUERY_RETRIES))
  })
})
