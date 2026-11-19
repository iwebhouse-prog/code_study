import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { routes } from '../../src/routes'
import { useAuthStore } from '../../src/stores/auth-store'
import { RAW_USER, errorReply, mockApiClient, restoreApiClient } from '../helpers/http'

function renderAt(entry: string | { pathname: string; state?: unknown }) {
  const router = createMemoryRouter(routes, { initialEntries: [entry] })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

const heading = () => screen.getByRole('heading', { level: 1 })

async function submit(buttonName: string, emailValue = 'a@b.com', passwordValue = 'abcd1234') {
  await userEvent.type(screen.getByLabelText('이메일'), emailValue)
  await userEvent.type(screen.getByLabelText('비밀번호'), passwordValue)
  await userEvent.click(screen.getByRole('button', { name: buttonName }))
}

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
  useAuthStore.getState().clearUser()
})

afterEach(() => {
  restoreApiClient()
})

describe('Register page', () => {
  it('shows the form and a link to the login page', async () => {
    const router = renderAt('/register')
    expect(heading()).toHaveTextContent('회원가입')
    await userEvent.click(screen.getByRole('link', { name: '로그인' }))
    expect(router.state.location.pathname).toBe('/login')
  })

  it('signs the new user in and goes to the dashboard', async () => {
    const calls = mockApiClient(() => ({ status: 201, data: RAW_USER }))
    const router = renderAt('/register')
    await submit('회원가입')
    expect(await screen.findByRole('heading', { name: '내 프로젝트' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
    expect(useAuthStore.getState().status).toBe('authenticated')
    expect(calls[0]).toMatchObject({
      url: '/auth/register',
      body: { email: 'a@b.com', password: 'abcd1234' },
    })
  })

  it('stays on the page and shows the server error', async () => {
    mockApiClient(() => errorReply(409, 'email_taken', '이미 가입된 이메일입니다.'))
    const router = renderAt('/register')
    await submit('회원가입')
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 가입된 이메일입니다.')
    expect(router.state.location.pathname).toBe('/register')
  })
})

describe('Login page', () => {
  it('shows the form and a link to the register page', async () => {
    const router = renderAt('/login')
    expect(heading()).toHaveTextContent('로그인')
    await userEvent.click(screen.getByRole('link', { name: '회원가입' }))
    expect(router.state.location.pathname).toBe('/register')
  })

  it('goes to the dashboard after signing in', async () => {
    mockApiClient(() => ({ status: 200, data: RAW_USER }))
    const router = renderAt('/login')
    await submit('로그인')
    expect(await screen.findByRole('heading', { name: '내 프로젝트' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })

  it('goes back to the page the visitor originally wanted', async () => {
    mockApiClient(() => ({ status: 200, data: RAW_USER }))
    const router = renderAt({ pathname: '/login', state: { from: '/projects/p-1?tab=2' } })
    await submit('로그인')
    expect(await screen.findByRole('heading', { name: '프로젝트 상세' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/projects/p-1')
    expect(router.state.location.search).toBe('?tab=2')
  })

  it.each(['//evil.example', 'https://evil.example', 42, null])(
    'ignores an unsafe target (%s) and goes to the dashboard',
    async (from) => {
      mockApiClient(() => ({ status: 200, data: RAW_USER }))
      const router = renderAt({ pathname: '/login', state: { from } })
      await submit('로그인')
      expect(await screen.findByRole('heading', { name: '내 프로젝트' })).toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/')
    },
  )

  it('shows the server message for wrong credentials and stays on the page', async () => {
    mockApiClient(() =>
      errorReply(401, 'invalid_credentials', '이메일 또는 비밀번호가 올바르지 않습니다.'),
    )
    const router = renderAt('/login')
    await submit('로그인')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '이메일 또는 비밀번호가 올바르지 않습니다.',
    )
    expect(router.state.location.pathname).toBe('/login')
    expect(useAuthStore.getState().status).toBe('anonymous')
  })
})

describe('protected pages', () => {
  it('send anonymous visitors to the login page, then back after sign-in', async () => {
    mockApiClient(() => ({ status: 200, data: RAW_USER }))
    const router = renderAt('/trash')
    expect(router.state.location.pathname).toBe('/login')
    await submit('로그인')
    expect(await screen.findByRole('heading', { name: '휴지통' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/trash')
  })

  it('wait without redirecting while the session is being checked', () => {
    useAuthStore.setState(useAuthStore.getInitialState(), true)
    const router = renderAt('/trash')
    expect(router.state.location.pathname).toBe('/trash')
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})
