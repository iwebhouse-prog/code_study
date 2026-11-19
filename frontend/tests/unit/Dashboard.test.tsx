import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createQueryClient } from '../../src/lib/queryClient'
import { routes } from '../../src/routes'
import { useAuthStore } from '../../src/stores/auth-store'
import { useToastStore } from '../../src/stores/toast-store'
import { APP_USER, errorReply, mockApiClient, restoreApiClient } from '../helpers/http'
import { RAW_PROJECT } from '../helpers/projects'

function renderDashboard() {
  const queryClient = createQueryClient()
  // No automatic retries: the error state should appear right away.
  queryClient.setDefaultOptions({ queries: { retry: false } })
  const router = createMemoryRouter(routes, { initialEntries: ['/'] })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, queryClient }
}

const SECOND = { ...RAW_PROJECT, id: '22222222-2222-4222-8222-222222222222', title: '계산기' }

beforeEach(() => {
  useAuthStore.getState().setUser(APP_USER)
  useToastStore.setState({ toasts: [] })
})

afterEach(() => {
  restoreApiClient()
})

describe('Dashboard: list', () => {
  it('shows a loading message while the projects load', async () => {
    mockApiClient(() => new Promise(() => undefined))
    renderDashboard()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('내 프로젝트')
    expect(await screen.findByText('프로젝트를 불러오는 중입니다…')).toBeInTheDocument()
  })

  it('shows a card for every project', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: [RAW_PROJECT, SECOND] }))
    renderDashboard()
    expect(await screen.findByRole('link', { name: 'My Todo App' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '계산기' })).toBeInTheDocument()
    expect(screen.getAllByText('완료 2/5 태스크')).toHaveLength(2)
    expect(calls[0]).toMatchObject({ method: 'get', url: '/projects' })
  })

  it('shows the empty state for a new user', async () => {
    mockApiClient(() => ({ status: 200, data: [] }))
    renderDashboard()
    expect(await screen.findByText('아직 프로젝트가 없습니다')).toBeInTheDocument()
    expect(
      screen.getByText(
        '프로젝트를 만들어 AI 코드 학습을 시작하세요. 프로젝트는 관련된 학습 태스크들을 모아둔 폴더입니다.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText("예: '나의 Todo 앱', '계산기 프로그램'")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '첫 프로젝트 만들기' })).toBeInTheDocument()
  })

  it('shows the API error message and retries on request', async () => {
    let failing = true
    mockApiClient(() =>
      failing
        ? errorReply(500, 'internal_error', '서버 오류가 발생했습니다.')
        : { status: 200, data: [RAW_PROJECT] },
    )
    renderDashboard()
    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.')
    failing = false
    await userEvent.click(screen.getByRole('button', { name: '다시 시도' }))
    expect(await screen.findByRole('link', { name: 'My Todo App' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('Dashboard: create project', () => {
  async function openFromHeader() {
    await screen.findByRole('link', { name: 'My Todo App' })
    await userEvent.click(screen.getByRole('button', { name: '새 프로젝트' }))
    return screen.getByRole('dialog', { name: '새 프로젝트' })
  }

  it('creates a project, refreshes the list, shows a toast and opens the new project', async () => {
    let projects = [RAW_PROJECT]
    const created = { ...SECOND, description: null }
    const calls = mockApiClient(({ method, url }) => {
      if (method === 'post') {
        projects = [created, ...projects]
        return { status: 201, data: created }
      }
      if (url === `/projects/${created.id}`) return { status: 200, data: created }
      return { status: 200, data: projects }
    })
    const { router } = renderDashboard()
    const dialog = await openFromHeader()
    await userEvent.type(within(dialog).getByLabelText('프로젝트 제목'), ' 계산기 ')
    await userEvent.click(within(dialog).getByRole('button', { name: '만들기' }))

    await waitFor(() => expect(router.state.location.pathname).toBe(`/projects/${created.id}`))
    expect(calls).toContainEqual(
      expect.objectContaining({ method: 'post', url: '/projects', body: { title: '계산기' } }),
    )
    expect(await screen.findByRole('heading', { level: 1, name: '계산기' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('프로젝트가 생성되었습니다.')
    // The list was asked for again, so going back to the dashboard shows the new project.
    const listCalls = calls.filter((c) => c.method === 'get' && c.url === '/projects')
    expect(listCalls.length).toBeGreaterThanOrEqual(2)
  })

  it('opens the same dialog from the empty state', async () => {
    mockApiClient(() => ({ status: 200, data: [] }))
    renderDashboard()
    await userEvent.click(await screen.findByRole('button', { name: '첫 프로젝트 만들기' }))
    expect(screen.getByRole('dialog', { name: '새 프로젝트' })).toBeInTheDocument()
  })

  it('keeps the dialog open and shows the server field error', async () => {
    mockApiClient(({ method }) =>
      method === 'post'
        ? errorReply(400, 'validation_error', '입력값 오류', {
            fields: [{ field: 'title', message: '이미 사용 중인 제목입니다.' }],
          })
        : { status: 200, data: [RAW_PROJECT] },
    )
    const { router } = renderDashboard()
    const dialog = await openFromHeader()
    await userEvent.type(within(dialog).getByLabelText('프로젝트 제목'), 'x')
    await userEvent.click(within(dialog).getByRole('button', { name: '만들기' }))
    expect(await within(dialog).findByText('이미 사용 중인 제목입니다.')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('can be cancelled', async () => {
    mockApiClient(() => ({ status: 200, data: [RAW_PROJECT] }))
    renderDashboard()
    const dialog = await openFromHeader()
    await userEvent.click(within(dialog).getByRole('button', { name: '취소' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
