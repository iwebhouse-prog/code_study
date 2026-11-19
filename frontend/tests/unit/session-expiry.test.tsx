// After 15 minutes the browser drops the access cookie (Max-Age = token
// lifetime), so the server answers `unauthorized`, not `token_expired`.
// The refresh cookie still lives for 7 days and must keep the user signed in.
import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSessionBootstrap } from '../../src/hooks/useAuth'
import { createQueryClient } from '../../src/lib/queryClient'
import { ApiError, createApiClient } from '../../src/services/api-client'
import { installSessionRefresh } from '../../src/services/auth-refresh'
import { useAuthStore } from '../../src/stores/auth-store'
import {
  APP_USER,
  RAW_USER,
  adapterFor,
  errorReply,
  mockApiClient,
  restoreApiClient,
  type Handler,
} from '../helpers/http'

function setup(handler: Handler, refreshImpl?: () => Promise<unknown>) {
  const client = createApiClient({
    baseURL: 'http://localhost:8000/api/v1',
    adapter: adapterFor(handler),
  })
  const refresh = vi.fn(refreshImpl ?? (() => Promise.resolve({})))
  const onSessionEnded = vi.fn()
  installSessionRefresh(client, { refresh, onSessionEnded })
  return { client, refresh, onSessionEnded }
}

/** First answer says the access cookie is gone; later answers succeed. */
function cookieGoneOnce(): Handler {
  let served = 0
  return () => {
    served += 1
    return served === 1 ? errorReply(401, 'unauthorized') : { status: 200, data: { ok: true } }
  }
}

describe('refresh when the access cookie has expired away', () => {
  it('refreshes once on unauthorized and retries the request once', async () => {
    const { client, refresh } = setup(cookieGoneOnce())
    const { data } = await client.get('/projects')
    expect(data).toEqual({ ok: true })
    expect(refresh).toHaveBeenCalledOnce()
  })

  it('shares one refresh between simultaneous unauthorized answers', async () => {
    let served = 0
    const { client, refresh } = setup(() => {
      served += 1
      return served <= 3 ? errorReply(401, 'unauthorized') : { status: 200, data: { ok: true } }
    })
    await Promise.all([client.get('/a'), client.get('/b'), client.get('/c')])
    expect(refresh).toHaveBeenCalledOnce()
  })

  it('does not refresh again when the retry is still unauthorized', async () => {
    const { client, refresh } = setup(() => errorReply(401, 'unauthorized'))
    await expect(client.get('/projects')).rejects.toMatchObject({ code: 'unauthorized' })
    expect(refresh).toHaveBeenCalledOnce()
  })

  it('without any session, reports the original unauthorized error', async () => {
    // A visitor who never signed in has no refresh cookie either; that is not
    // a session ending, so only the caller decides what to do.
    const { client, onSessionEnded } = setup(
      () => errorReply(401, 'unauthorized'),
      () => Promise.reject(new ApiError({ status: 401, code: 'session_expired', message: '' })),
    )
    await expect(client.get('/projects')).rejects.toMatchObject({ code: 'unauthorized' })
    expect(onSessionEnded).not.toHaveBeenCalled()
  })
})

describe('opening the app after the access cookie expired', () => {
  const queryClient = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  beforeEach(() => {
    useAuthStore.setState(useAuthStore.getInitialState(), true)
  })

  afterEach(() => {
    restoreApiClient()
  })

  it('stays signed in by refreshing with the 7-day cookie', async () => {
    let meCalls = 0
    const calls = mockApiClient((request) => {
      if (request.url === '/auth/refresh') return { status: 200, data: RAW_USER }
      meCalls += 1
      return meCalls === 1 ? errorReply(401, 'unauthorized') : { status: 200, data: RAW_USER }
    })
    renderHook(() => useSessionBootstrap(), { wrapper })
    await waitFor(() => expect(useAuthStore.getState().status).toBe('authenticated'))
    expect(useAuthStore.getState().user).toEqual(APP_USER)
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      'get /auth/me',
      'post /auth/refresh',
      'get /auth/me',
    ])
  })

  it('treats a visitor without any session as signed out after one refresh try', async () => {
    const calls = mockApiClient((request) =>
      request.url === '/auth/refresh'
        ? errorReply(401, 'session_expired')
        : errorReply(401, 'unauthorized'),
    )
    renderHook(() => useSessionBootstrap(), { wrapper })
    await waitFor(() => expect(useAuthStore.getState().status).toBe('anonymous'))
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(['get /auth/me', 'post /auth/refresh'])
  })
})
