import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { apiClient } from '../services/api-client'
import { installSessionRefresh } from '../services/auth-refresh'
import { authService, type Credentials } from '../services/auth-service'
import { useAuthStore, type AuthUser } from '../stores/auth-store'

/**
 * Runs once at app start: keeps access cookies renewed (single-flight refresh),
 * ends the session on `session_expired`, and asks GET /auth/me who is signed in.
 */
export function useSessionBootstrap(): void {
  const queryClient = useQueryClient()

  useEffect(
    () =>
      installSessionRefresh(apiClient, {
        refresh: authService.refresh,
        onSessionEnded: () => {
          useAuthStore.getState().clearUser()
          queryClient.clear()
        },
      }),
    [queryClient],
  )

  useEffect(() => {
    if (useAuthStore.getState().status !== 'unknown') return
    // A sign-in that finishes while the check runs wins over its answer.
    const ifStillUnknown = (apply: () => void) => {
      if (useAuthStore.getState().status === 'unknown') apply()
    }
    authService.me().then(
      (user) => ifStillUnknown(() => useAuthStore.getState().setUser(user)),
      () => ifStillUnknown(() => useAuthStore.getState().clearUser()),
    )
  }, [])
}

// Kept apart from useLogout: the sign-in pages only need this part, and must not
// require a QueryClientProvider.
export function useAuth() {
  const status = useAuthStore((state) => state.status)
  const user = useAuthStore((state) => state.user)

  const signInWith =
    (request: (credentials: Credentials) => Promise<AuthUser>) =>
    async (credentials: Credentials) => {
      useAuthStore.getState().setUser(await request(credentials))
    }

  return {
    status,
    user,
    login: signInWith(authService.login),
    register: signInWith(authService.register),
  }
}

/** Signs out here even if the server cannot be told, and forgets cached data. */
export function useLogout() {
  const queryClient = useQueryClient()
  return async () => {
    try {
      await authService.logout()
    } catch {
      // The cookies expire on their own; the local sign-out must still happen.
    }
    useAuthStore.getState().clearUser()
    queryClient.clear()
  }
}
