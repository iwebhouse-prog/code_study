import { QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import App from '../../src/App'
import { createQueryClient } from '../../src/lib/queryClient'
import { paths } from '../../src/lib/paths'
import { routes } from '../../src/routes'
import { useAuthStore } from '../../src/stores/auth-store'
import { APP_USER, mockApiClient, restoreApiClient } from '../helpers/http'
import { RAW_PROJECT } from '../helpers/projects'
import { RAW_TASK } from '../helpers/tasks'

// The signed-in pages need a signed-in user and talk to the project API.
beforeEach(() => {
  useAuthStore.getState().setUser(APP_USER)
  mockApiClient(({ url }) => {
    if (url === '/projects') return { status: 200, data: [] }
    if (url.startsWith('/tasks/')) return { status: 200, data: RAW_TASK }
    return { status: 200, data: { ...RAW_PROJECT, id: url.replace('/projects/', '') } }
  })
})

afterEach(() => {
  restoreApiClient()
})

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <QueryClientProvider client={createQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

function pageHeading() {
  return screen.getByRole('heading', { level: 1 })
}

describe('App routes', () => {
  it.each([
    ['/', '내 프로젝트'],
    ['/login', '로그인'],
    ['/register', '회원가입'],
    ['/trash', '휴지통'],
  ])('%s shows the %s page', (path, title) => {
    renderAt(path)
    expect(pageHeading()).toHaveTextContent(title)
  })

  it('/projects/p-1 shows the project detail page', async () => {
    renderAt('/projects/p-1')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'My Todo App' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: '태스크' })).toBeInTheDocument()
  })

  it('passes the project id from the URL to the page', async () => {
    const calls = mockApiClient(({ url }) => ({
      status: 200,
      data: { ...RAW_PROJECT, id: url.replace('/projects/', '') },
    }))
    renderAt('/projects/abc-123')
    await screen.findByRole('heading', { level: 1, name: 'My Todo App' })
    expect(calls[0]).toMatchObject({ method: 'get', url: '/projects/abc-123' })
  })

  it('/tasks/t-1 shows the task detail page', async () => {
    renderAt('/tasks/t-1')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Task 1. 할 일 추가 기능' }),
    ).toBeInTheDocument()
  })

  it('passes the task id from the URL to the page', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_TASK }))
    renderAt('/tasks/task-9')
    await screen.findByRole('heading', { level: 1, name: 'Task 1. 할 일 추가 기능' })
    expect(calls[0]).toMatchObject({ method: 'get', url: '/tasks/task-9' })
  })

  it('shows a Korean not-found page for unknown paths', () => {
    renderAt('/no/such/page')
    expect(pageHeading()).toHaveTextContent('페이지를 찾을 수 없습니다')
    expect(screen.getByText('요청한 페이지를 찾을 수 없습니다.')).toBeInTheDocument()
  })

  it('not-found page links back to the dashboard', async () => {
    const router = renderAt('/no/such/page')
    await userEvent.click(screen.getByRole('link', { name: '내 프로젝트로 이동' }))
    expect(router.state.location.pathname).toBe('/')
    expect(pageHeading()).toHaveTextContent('내 프로젝트')
    await screen.findByText('아직 프로젝트가 없습니다')
  })

  it('browser back returns to the previous page', async () => {
    const router = renderAt('/trash')
    await act(() => router.navigate(paths.project('p-1')))
    expect(
      await screen.findByRole('heading', { level: 1, name: 'My Todo App' }),
    ).toBeInTheDocument()
    await act(() => router.navigate(-1))
    expect(pageHeading()).toHaveTextContent('휴지통')
  })
})

describe('paths', () => {
  it('builds URLs that match the routes', () => {
    expect(paths.dashboard).toBe('/')
    expect(paths.login).toBe('/login')
    expect(paths.register).toBe('/register')
    expect(paths.trash).toBe('/trash')
    expect(paths.project('p 1')).toBe('/projects/p%201')
    expect(paths.task('t/2')).toBe('/tasks/t%2F2')
  })
})

describe('App', () => {
  it('renders the router in the browser', () => {
    window.history.pushState({}, '', '/login')
    render(<App />)
    expect(pageHeading()).toHaveTextContent('로그인')
  })
})
