import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createQueryClient } from '../../src/lib/queryClient'
import { routes } from '../../src/routes'
import { useAuthStore } from '../../src/stores/auth-store'
import { APP_USER, errorReply, mockApiClient, restoreApiClient } from '../helpers/http'
import { RAW_TASK } from '../helpers/tasks'

const TASK_URL = `/tasks/${RAW_TASK.id}`

function renderTask() {
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false } })
  const router = createMemoryRouter(routes, { initialEntries: [TASK_URL] })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router }
}

beforeEach(() => {
  useAuthStore.getState().setUser(APP_USER)
})

afterEach(() => {
  restoreApiClient()
})

describe('TaskDetail', () => {
  it('shows a loading message first', () => {
    mockApiClient(() => new Promise(() => undefined))
    renderTask()
    expect(screen.getByText('태스크를 불러오는 중입니다…')).toBeInTheDocument()
  })

  it('loads the task named in the URL and shows "Task {n}. {title}"', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_TASK }))
    renderTask()
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Task 1. 할 일 추가 기능' }),
    ).toBeInTheDocument()
    expect(calls[0]).toMatchObject({ method: 'get', url: TASK_URL })
    expect(screen.getByText('버튼을 누르면 목록에 추가')).toBeInTheDocument()
  })

  it('has no description line when the description is null', async () => {
    mockApiClient(() => ({ status: 200, data: { ...RAW_TASK, description: null } }))
    renderTask()
    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByText('버튼을 누르면 목록에 추가')).not.toBeInTheDocument()
  })

  it('links back to the project of the task', async () => {
    mockApiClient(() => ({ status: 200, data: RAW_TASK }))
    const { router } = renderTask()
    await userEvent.click(await screen.findByRole('link', { name: '프로젝트로 돌아가기' }))
    expect(router.state.location.pathname).toBe(`/projects/${RAW_TASK.project_id}`)
  })

  it('has the three tabs, starting on the document tab', async () => {
    mockApiClient(() => ({ status: 200, data: RAW_TASK }))
    renderTask()
    await screen.findByRole('heading', { level: 1 })
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map((tab) => tab.textContent)).toEqual(['학습 문서', '연습 문제', '질문하기'])
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel', { name: '학습 문서' })).toBeInTheDocument()
  })

  it.each(['연습 문제', '질문하기', '학습 문서'])('switches to the %s tab', async (name) => {
    mockApiClient(() => ({ status: 200, data: RAW_TASK }))
    renderTask()
    await userEvent.click(await screen.findByRole('tab', { name }))
    expect(screen.getByRole('tab', { name })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel', { name })).toBeInTheDocument()
  })

  it.each([
    [403, 'forbidden', '이 태스크에 접근할 권한이 없습니다.'],
    [404, 'not_found', '요청한 태스크를 찾을 수 없습니다.'],
  ])('shows the API message and a way back on %i', async (status, code, message) => {
    mockApiClient(() => errorReply(status, code, message))
    const { router } = renderTask()
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(
      screen.getByRole('heading', { level: 1, name: '태스크를 열 수 없습니다' }),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: '내 프로젝트로 돌아가기' }))
    expect(router.state.location.pathname).toBe('/')
  })
})
