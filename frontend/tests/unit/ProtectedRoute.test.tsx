import { render, screen } from '@testing-library/react'
import { act } from 'react'
import { RouterProvider, createMemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import ProtectedRoute from '../../src/components/auth/ProtectedRoute'
import { useAuthStore } from '../../src/stores/auth-store'
import { APP_USER } from '../helpers/http'

function LoginProbe() {
  const location = useLocation()
  return <p>login page, from={(location.state as { from?: string } | null)?.from ?? 'none'}</p>
}

function renderAt(path: string) {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginProbe /> },
      {
        element: <ProtectedRoute />,
        children: [{ path: '/secret', element: <p>secret page</p> }],
      },
      { path: '/direct', element: <ProtectedRoute>direct child</ProtectedRoute> },
    ],
    { initialEntries: [path] },
  )
  render(<RouterProvider router={router} />)
  return router
}

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
})

describe('ProtectedRoute', () => {
  it('shows a loading indicator and does not redirect while the session is unknown', () => {
    const router = renderAt('/secret')
    expect(screen.getByRole('status')).toHaveTextContent('확인')
    expect(screen.queryByText('secret page')).not.toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/secret')
  })

  it('redirects anonymous visitors to /login and remembers the target', () => {
    useAuthStore.getState().clearUser()
    const router = renderAt('/secret?tab=2#part')
    expect(router.state.location.pathname).toBe('/login')
    expect(screen.getByText('login page, from=/secret?tab=2#part')).toBeInTheDocument()
  })

  it('renders the nested route for authenticated users', () => {
    useAuthStore.getState().setUser(APP_USER)
    renderAt('/secret')
    expect(screen.getByText('secret page')).toBeInTheDocument()
  })

  it('renders its children when given any', () => {
    useAuthStore.getState().setUser(APP_USER)
    renderAt('/direct')
    expect(screen.getByText('direct child')).toBeInTheDocument()
  })

  it('moves from loading to the page when the check finishes', () => {
    renderAt('/secret')
    act(() => useAuthStore.getState().setUser(APP_USER))
    expect(screen.getByText('secret page')).toBeInTheDocument()
  })

  it('moves from the page to /login when the session ends', () => {
    useAuthStore.getState().setUser(APP_USER)
    const router = renderAt('/secret')
    act(() => useAuthStore.getState().clearUser())
    expect(router.state.location.pathname).toBe('/login')
  })
})
