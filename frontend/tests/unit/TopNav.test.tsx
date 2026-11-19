import { QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createQueryClient } from '../../src/lib/queryClient'
import { routes } from '../../src/routes'
import { useAuthStore } from '../../src/stores/auth-store'
import { APP_USER, mockApiClient, restoreApiClient } from '../helpers/http'

function renderAt(path: string) {
  const queryClient = createQueryClient()
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, queryClient }
}

const nav = () => screen.getByRole('navigation', { name: '주 메뉴' })

async function openUserMenu() {
  const trigger = within(nav()).getByRole('button', { name: /student@example\.com/ })
  act(() => trigger.focus())
  await userEvent.keyboard('{Enter}')
  return screen.findByRole('menu')
}

beforeEach(() => {
  useAuthStore.getState().setUser(APP_USER)
})

afterEach(() => {
  restoreApiClient()
})

describe('top navigation bar', () => {
  it('shows the logo, the menu and the signed-in email on signed-in pages', () => {
    renderAt('/')
    const bar = within(nav())
    expect(bar.getByRole('link', { name: 'CodeLearn' })).toHaveAttribute('href', '/')
    expect(bar.getByRole('link', { name: '대시보드' })).toHaveAttribute('href', '/')
    expect(bar.getByText('student@example.com')).toBeInTheDocument()
  })

  it('marks the current page', () => {
    renderAt('/')
    expect(within(nav()).getByRole('link', { name: '대시보드' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('does not mark the dashboard on other pages', () => {
    renderAt('/trash')
    expect(within(nav()).getByRole('link', { name: '대시보드' })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('shows the progress menu as not available yet', () => {
    renderAt('/')
    const progress = within(nav()).getByText('학습 진행률')
    expect(progress).toHaveAttribute('aria-disabled', 'true')
    expect(within(nav()).queryByRole('link', { name: '학습 진행률' })).not.toBeInTheDocument()
  })

  it('keeps one page heading: the bar adds no h1', () => {
    renderAt('/trash')
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('휴지통')
  })

  it.each(['/login', '/register'])('is not shown on %s', (path) => {
    useAuthStore.getState().clearUser()
    renderAt(path)
    expect(screen.queryByRole('navigation', { name: '주 메뉴' })).not.toBeInTheDocument()
  })
})

describe('user menu', () => {
  it('opens with the keyboard and offers logout', async () => {
    renderAt('/')
    const menu = await openUserMenu()
    expect(within(menu).getByRole('menuitem', { name: '로그아웃' })).toBeInTheDocument()
  })

  it('logout tells the server, forgets the session and goes to the login page', async () => {
    const calls = mockApiClient(() => ({ status: 204 }))
    const { router, queryClient } = renderAt('/trash')
    queryClient.setQueryData(['projects'], [1])
    const menu = await openUserMenu()
    await userEvent.click(within(menu).getByRole('menuitem', { name: '로그아웃' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('로그인')
    expect(calls).toContainEqual(expect.objectContaining({ method: 'post', url: '/auth/logout' }))
    await waitFor(() => expect(useAuthStore.getState().status).toBe('anonymous'))
    expect(queryClient.getQueryData(['projects'])).toBeUndefined()
    // A fresh sign-in after logout starts at the dashboard, not the old page.
    expect(router.state.location.state).toBeNull()
  })

  it('still signs out when the server cannot be reached', async () => {
    mockApiClient(() => {
      throw new Error('offline')
    })
    const { router } = renderAt('/')
    const menu = await openUserMenu()
    await userEvent.click(within(menu).getByRole('menuitem', { name: '로그아웃' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    await waitFor(() => expect(useAuthStore.getState().status).toBe('anonymous'))
  })
})
