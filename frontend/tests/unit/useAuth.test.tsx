import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useAuth, useLogout, useSessionBootstrap } from '../../src/hooks/useAuth'
import { apiClient } from '../../src/services/api-client'
import { useAuthStore } from '../../src/stores/auth-store'
import {
  APP_USER,
  RAW_USER,
  errorReply,
  mockApiClient,
  restoreApiClient,
  type Handler,
} from '../helpers/http'

let queryClient: QueryClient

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
  queryClient = new QueryClient()
})

afterEach(() => {
  restoreApiClient()
})

const status = () => useAuthStore.getState().status

describe('useSessionBootstrap', () => {
  it('signs the user in when GET /auth/me answers', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_USER }))
    renderHook(() => useSessionBootstrap(), { wrapper })
    await waitFor(() => expect(status()).toBe('authenticated'))
    expect(useAuthStore.getState().user).toEqual(APP_USER)
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(['get /auth/me'])
  })

  it('marks the visitor anonymous when there is no session', async () => {
    mockApiClient(() => errorReply(401, 'unauthorized'))
    renderHook(() => useSessionBootstrap(), { wrapper })
    await waitFor(() => expect(status()).toBe('anonymous'))
  })

  it('marks the visitor anonymous when the server cannot be reached', async () => {
    mockApiClient(() => {
      throw new Error('offline')
    })
    renderHook(() => useSessionBootstrap(), { wrapper })
    await waitFor(() => expect(status()).toBe('anonymous'))
  })

  it('refreshes silently and asks again when the access cookie has expired', async () => {
    let meCalls = 0
    const handler: Handler = (req) => {
      if (req.url === '/auth/refresh') return { status: 200, data: RAW_USER }
      meCalls += 1
      return meCalls === 1 ? errorReply(401, 'token_expired') : { status: 200, data: RAW_USER }
    }
    const calls = mockApiClient(handler)
    renderHook(() => useSessionBootstrap(), { wrapper })
    await waitFor(() => expect(status()).toBe('authenticated'))
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      'get /auth/me',
      'post /auth/refresh',
      'get /auth/me',
    ])
  })

  it('does not ask again when the state is already known', () => {
    useAuthStore.getState().setUser(APP_USER)
    const calls = mockApiClient(() => ({ status: 200, data: RAW_USER }))
    renderHook(() => useSessionBootstrap(), { wrapper })
    expect(calls).toHaveLength(0)
  })

  it('does not overwrite a sign-in that happened while the check was running', async () => {
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    mockApiClient(async () => {
      await gate
      return errorReply(401, 'unauthorized')
    })
    renderHook(() => useSessionBootstrap(), { wrapper })
    act(() => useAuthStore.getState().setUser(APP_USER))
    release()
    await act(() => gate)
    expect(status()).toBe('authenticated')
  })

  it('clears the user and the query cache when the session ends later', async () => {
    useAuthStore.getState().setUser(APP_USER)
    queryClient.setQueryData(['projects'], [1, 2])
    mockApiClient(() => errorReply(401, 'session_expired'))
    renderHook(() => useSessionBootstrap(), { wrapper })
    await expect(apiClient.get('/projects')).rejects.toMatchObject({ code: 'session_expired' })
    expect(status()).toBe('anonymous')
    expect(queryClient.getQueryData(['projects'])).toBeUndefined()
  })

  it('clears everything when the silent refresh fails', async () => {
    useAuthStore.getState().setUser(APP_USER)
    queryClient.setQueryData(['projects'], [1, 2])
    mockApiClient((req) =>
      req.url === '/auth/refresh'
        ? errorReply(401, 'session_expired')
        : errorReply(401, 'token_expired'),
    )
    renderHook(() => useSessionBootstrap(), { wrapper })
    await expect(apiClient.get('/projects')).rejects.toMatchObject({ code: 'session_expired' })
    expect(status()).toBe('anonymous')
    expect(queryClient.getQueryData(['projects'])).toBeUndefined()
  })

  it('stops watching for expired sessions after unmount', async () => {
    useAuthStore.getState().setUser(APP_USER)
    mockApiClient(() => errorReply(401, 'session_expired'))
    const { unmount } = renderHook(() => useSessionBootstrap(), { wrapper })
    unmount()
    await expect(apiClient.get('/projects')).rejects.toMatchObject({ code: 'session_expired' })
    expect(status()).toBe('authenticated')
  })
})

describe('useAuth', () => {
  it('exposes the store state', () => {
    useAuthStore.getState().setUser(APP_USER)
    const { result } = renderHook(() => useAuth(), { wrapper })
    expect(result.current.status).toBe('authenticated')
    expect(result.current.user).toEqual(APP_USER)
  })

  it('login signs the user in', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_USER }))
    const { result } = renderHook(() => useAuth(), { wrapper })
    await act(() => result.current.login({ email: 'a@b.com', password: 'abcd1234' }))
    expect(status()).toBe('authenticated')
    expect(useAuthStore.getState().user).toEqual(APP_USER)
    expect(calls[0]).toMatchObject({ url: '/auth/login' })
  })

  it('register signs the user in (the server sets the cookies)', async () => {
    const calls = mockApiClient(() => ({ status: 201, data: RAW_USER }))
    const { result } = renderHook(() => useAuth(), { wrapper })
    await act(() => result.current.register({ email: 'a@b.com', password: 'abcd1234' }))
    expect(status()).toBe('authenticated')
    expect(calls[0]).toMatchObject({ url: '/auth/register' })
  })

  it('a failed login rejects and leaves the state alone', async () => {
    mockApiClient(() => errorReply(401, 'invalid_credentials'))
    const { result } = renderHook(() => useAuth(), { wrapper })
    await expect(
      act(() => result.current.login({ email: 'a@b.com', password: 'wrong123' })),
    ).rejects.toMatchObject({ code: 'invalid_credentials' })
    expect(status()).toBe('unknown')
  })

  it('logout calls the API, then clears the user and the query cache', async () => {
    useAuthStore.getState().setUser(APP_USER)
    queryClient.setQueryData(['projects'], [1])
    const calls = mockApiClient(() => ({ status: 204 }))
    const { result } = renderHook(() => useLogout(), { wrapper })
    await act(() => result.current())
    expect(calls[0]).toMatchObject({ method: 'post', url: '/auth/logout' })
    expect(status()).toBe('anonymous')
    expect(queryClient.getQueryData(['projects'])).toBeUndefined()
  })

  it('logout signs out locally even when the server cannot be reached', async () => {
    useAuthStore.getState().setUser(APP_USER)
    queryClient.setQueryData(['projects'], [1])
    mockApiClient(() => {
      throw new Error('offline')
    })
    const { result } = renderHook(() => useLogout(), { wrapper })
    await act(() => result.current())
    expect(status()).toBe('anonymous')
    expect(queryClient.getQueryData(['projects'])).toBeUndefined()
  })
})
