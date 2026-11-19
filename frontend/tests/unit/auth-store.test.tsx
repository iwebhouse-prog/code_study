import { act, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { type AuthUser, useAuthStore } from '../../src/stores/auth-store'

const USER: AuthUser = {
  id: '12345678-1234-5678-1234-567812345678',
  email: 'student@example.com',
  skillLevel: 'Complete Beginner',
}

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
  localStorage.clear()
  sessionStorage.clear()
})

describe('auth store', () => {
  it('starts as unknown until the session has been checked', () => {
    const state = useAuthStore.getState()
    expect(state.status).toBe('unknown')
    expect(state.user).toBeNull()
  })

  it('setUser marks the session as authenticated', () => {
    useAuthStore.getState().setUser(USER)
    const state = useAuthStore.getState()
    expect(state.status).toBe('authenticated')
    expect(state.user).toEqual(USER)
  })

  it('clearUser marks the session as anonymous', () => {
    useAuthStore.getState().setUser(USER)
    useAuthStore.getState().clearUser()
    const state = useAuthStore.getState()
    expect(state.status).toBe('anonymous')
    expect(state.user).toBeNull()
  })

  it('clearUser from unknown means the check found no session', () => {
    useAuthStore.getState().clearUser()
    expect(useAuthStore.getState().status).toBe('anonymous')
  })

  it('never holds tokens: they stay in HTTPOnly cookies', () => {
    useAuthStore.getState().setUser(USER)
    expect(Object.keys(useAuthStore.getState()).sort()).toEqual([
      'clearUser',
      'setUser',
      'status',
      'user',
    ])
  })

  it('writes nothing to browser storage', () => {
    // After a refresh the session comes from the cookie (GET /auth/me), so a
    // stored copy could only go stale or expose the email to scripts.
    useAuthStore.getState().setUser(USER)
    expect(localStorage).toHaveLength(0)
    expect(sessionStorage).toHaveLength(0)
  })
})

function Greeting() {
  const email = useAuthStore((state) => state.user?.email)
  return <p>{email ?? '로그인 전'}</p>
}

describe('useAuthStore in components', () => {
  it('re-renders when the user changes', () => {
    render(<Greeting />)
    expect(screen.getByText('로그인 전')).toBeInTheDocument()
    act(() => useAuthStore.getState().setUser(USER))
    expect(screen.getByText('student@example.com')).toBeInTheDocument()
    act(() => useAuthStore.getState().clearUser())
    expect(screen.getByText('로그인 전')).toBeInTheDocument()
  })
})
