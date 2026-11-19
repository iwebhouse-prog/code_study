import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import { ApiError } from './api-client'
import { REFRESH_PATH } from './auth-service'

const RETRIED = '__retriedAfterRefresh'
const refreshesInFlight = new WeakMap<AxiosInstance, Promise<unknown>>()
type MaybeRetried = InternalAxiosRequestConfig & { [RETRIED]?: true }

interface Options {
  /** Calls POST /auth/refresh. */
  refresh: () => Promise<unknown>
  /** The session is over: forget the user and cached data. */
  onSessionEnded: () => void
}

// Quietly renews the 15-minute access cookie: on `token_expired` refresh once,
// then repeat the request once. `unauthorized` gets the same treatment: the
// access cookie's Max-Age equals the token lifetime, so after 15 minutes the
// browser drops it and the server sees no cookie at all, while the 7-day
// refresh cookie may still be valid. Only one refresh runs at a time because
// reusing an already rotated refresh token logs the user out everywhere
// (contracts/auth-api.md). Returns a function that removes the interceptor.
export function installSessionRefresh(
  client: AxiosInstance,
  { refresh, onSessionEnded }: Options,
): () => void {
  // Kept per client, not per install: React StrictMode installs this twice in
  // development, and a request sent before the reinstall still runs through
  // the first interceptor. Both must wait on the same refresh.
  const refreshOnce = () => {
    let inFlight = refreshesInFlight.get(client)
    if (!inFlight) {
      inFlight = refresh().finally(() => refreshesInFlight.delete(client))
      refreshesInFlight.set(client, inFlight)
    }
    return inFlight
  }

  const id = client.interceptors.response.use(undefined, async (error: unknown) => {
    if (!(error instanceof ApiError)) throw error
    if (error.code === 'session_expired') {
      onSessionEnded()
      throw error
    }
    const config = error.config as MaybeRetried | undefined
    const renewable = error.code === 'token_expired' || error.code === 'unauthorized'
    if (!renewable || !config || config[RETRIED] || config.url === REFRESH_PATH) {
      throw error
    }
    try {
      await refreshOnce()
    } catch (refreshError) {
      if (error.code === 'unauthorized') {
        // No usable session either way (a visitor who never signed in has no
        // refresh cookie): report the original answer. A server that rejects
        // the refresh says session_expired, which ends a real session above.
        throw error
      }
      onSessionEnded()
      throw refreshError
    }
    return client.request({ ...config, [RETRIED]: true } as MaybeRetried)
  })
  return () => client.interceptors.response.eject(id)
}
