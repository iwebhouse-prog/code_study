// React StrictMode (development) runs effects twice: the refresh interceptor is
// installed, removed and installed again, and a request already sent keeps the
// first one. Both must still share ONE refresh: a second refresh with the same
// token counts as theft and ends every session (T026).
import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { StrictMode, type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSessionBootstrap } from '../../src/hooks/useAuth'
import { createQueryClient } from '../../src/lib/queryClient'
import { createApiClient } from '../../src/services/api-client'
import { installSessionRefresh } from '../../src/services/auth-refresh'
import { useAuthStore } from '../../src/stores/auth-store'
import { RAW_USER, adapterFor, errorReply, mockApiClient, restoreApiClient } from '../helpers/http'

describe('one refresh per client, however often the interceptor is installed', () => {
  it('a request sent before reinstalling shares the refresh with one sent after', async () => {
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    let served = 0
    const client = createApiClient({
      baseURL: 'http://localhost:8000/api/v1',
      adapter: adapterFor(async () => {
        served += 1
        if (served <= 2) {
          await gate
          return errorReply(401, 'unauthorized')
        }
        return { status: 200, data: { ok: true } }
      }),
    })
    const refresh = vi.fn(() => Promise.resolve({}))
    const options = { refresh, onSessionEnded: vi.fn() }

    const uninstallFirst = installSessionRefresh(client, options)
    const first = client.get('/auth/me')
    uninstallFirst()
    installSessionRefresh(client, options)
    const second = client.get('/auth/me')
    release()

    await Promise.all([first, second])
    expect(refresh).toHaveBeenCalledOnce()
  })
})

describe('app start under StrictMode after the access cookie expired', () => {
  const queryClient = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <StrictMode>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </StrictMode>
  )

  beforeEach(() => {
    useAuthStore.setState(useAuthStore.getInitialState(), true)
  })

  afterEach(() => {
    restoreApiClient()
  })

  it('refreshes once and stays signed in', async () => {
    let refreshed = false
    const calls = mockApiClient((request) => {
      if (request.url === '/auth/refresh') {
        // A second refresh with the rotated token would be refused as reuse.
        if (refreshed) return errorReply(401, 'session_expired')
        refreshed = true
        return { status: 200, data: RAW_USER }
      }
      return refreshed ? { status: 200, data: RAW_USER } : errorReply(401, 'unauthorized')
    })
    renderHook(() => useSessionBootstrap(), { wrapper })
    await waitFor(() => expect(useAuthStore.getState().status).toBe('authenticated'))
    expect(calls.filter((c) => c.url === '/auth/refresh')).toHaveLength(1)
  })
})
