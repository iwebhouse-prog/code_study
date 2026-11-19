import { create } from 'zustand'

export interface AuthUser {
  id: string
  email: string
  skillLevel: string
}

// 'unknown' lasts from page load until the session check (GET /auth/me)
// answers; treating it as signed out would bounce signed-in users to /login.
export type AuthStatus = 'unknown' | 'authenticated' | 'anonymous'

interface AuthState {
  status: AuthStatus
  user: AuthUser | null
  setUser: (user: AuthUser) => void
  clearUser: () => void
}

// Holds who is signed in, never the JWTs: those stay in HTTPOnly cookies
// (research.md section 8), out of reach of any script running on the page.
// Not persisted either, because the cookie decides the session after a refresh.
export const useAuthStore = create<AuthState>()((set) => ({
  status: 'unknown',
  user: null,
  setUser: (user) => set({ status: 'authenticated', user }),
  clearUser: () => set({ status: 'anonymous', user: null }),
}))
