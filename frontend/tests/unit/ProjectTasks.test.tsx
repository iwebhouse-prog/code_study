import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createQueryClient } from '../../src/lib/queryClient'
import { routes } from '../../src/routes'
import { useAuthStore } from '../../src/stores/auth-store'
import { useToastStore } from '../../src/stores/toast-store'
import {
  APP_USER,
  errorReply,
  mockApiClient,
  restoreApiClient,
  type Handler,
  type Reply,
} from '../helpers/http'
import { RAW_PROJECT } from '../helpers/projects'
import { RAW_TASK, RAW_UPLOAD_RESULT } from '../helpers/tasks'

const PROJECT_URL = `/projects/${RAW_PROJECT.id}`
const TASKS_URL = `${PROJECT_URL}/tasks`

function renderDetail() {
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false } })
  const router = createMemoryRouter(routes, { initialEntries: [PROJECT_URL] })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router }
}

/** Project and task list; `tasks` is what GET .../tasks answers with. */
function api(tasks: Reply | (() => Reply)): Handler {
  return ({ method, url }) => {
    if (url === TASKS_URL && method === 'get') return typeof tasks === 'function' ? tasks() : tasks
    if (url === TASKS_URL && method === 'post') return { status: 201, data: RAW_UPLOAD_RESULT }
    if (url.startsWith('/tasks/')) return { status: 200, data: RAW_TASK }
    return { status: 200, data: RAW_PROJECT }
  }
}

const task = (number: number, title: string) => ({
  ...RAW_TASK,
  id: `task-${number}`,
  task_number: number,
  title,
})

beforeEach(() => {
  useAuthStore.getState().setUser(APP_USER)
  useToastStore.setState({ toasts: [] })
})

afterEach(() => {
  restoreApiClient()
})

describe('ProjectDetail: task list', () => {
  it('loads the tasks of the project and shows a loading message first', async () => {
    const calls = mockApiClient(api({ status: 200, data: [] }))
    renderDetail()
    await screen.findByRole('heading', { level: 2, name: '태스크' })
    expect(await screen.findByText('아직 태스크가 없습니다')).toBeInTheDocument()
    expect(calls).toContainEqual(expect.objectContaining({ method: 'get', url: TASKS_URL }))
  })

  it('shows the loading message while the tasks load', async () => {
    mockApiClient(api({ status: 200, data: [] }))
    renderDetail()
    expect(await screen.findByText('태스크를 불러오는 중입니다…')).toBeInTheDocument()
  })

  it('shows the empty state from the contract', async () => {
    mockApiClient(api({ status: 200, data: [] }))
    renderDetail()
    expect(await screen.findByText('아직 태스크가 없습니다')).toBeInTheDocument()
    expect(
      screen.getByText('코드를 업로드하고 학습 자료를 생성하려면 태스크를 추가하세요.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('💡 팁: 작은 코드 단위로 나누어 학습하면 이해가 쉬워집니다.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '첫 태스크 추가' })).toBeInTheDocument()
  })

  it('shows task cards in task_number order', async () => {
    mockApiClient(api({ status: 200, data: [task(2, '두 번째'), task(1, '첫 번째')] }))
    renderDetail()
    await screen.findByText('첫 번째')
    const list = screen.getByRole('list', { name: '태스크 목록' })
    const titles = within(list)
      .getAllByRole('link')
      .map((link) => link.textContent)
    expect(titles).toEqual(['첫 번째', '두 번째'])
    expect(screen.queryByText('아직 태스크가 없습니다')).not.toBeInTheDocument()
  })

  it('links a card to its task page', async () => {
    mockApiClient(api({ status: 200, data: [task(1, '첫 번째')] }))
    const { router } = renderDetail()
    await userEvent.click(await screen.findByRole('link', { name: '첫 번째' }))
    expect(router.state.location.pathname).toBe('/tasks/task-1')
  })

  it('shows the API message and can retry when loading fails', async () => {
    let fail = true
    mockApiClient(
      api(() =>
        fail ? errorReply(500, 'internal_error', '서버 오류') : { status: 200, data: [] },
      ),
    )
    renderDetail()
    expect(await screen.findByText('서버 오류')).toBeInTheDocument()
    fail = false
    await userEvent.click(screen.getByRole('button', { name: '다시 시도' }))
    expect(await screen.findByText('아직 태스크가 없습니다')).toBeInTheDocument()
  })
})

describe('ProjectDetail: creating a task', () => {
  it('opens the dialog from the add button when tasks exist', async () => {
    mockApiClient(api({ status: 200, data: [task(1, '첫 번째')] }))
    renderDetail()
    await screen.findByText('첫 번째')
    await userEvent.click(screen.getByRole('button', { name: '태스크 추가' }))
    expect(screen.getByRole('dialog', { name: '새 태스크' })).toBeInTheDocument()
  })

  it('opens the dialog from the empty state button', async () => {
    mockApiClient(api({ status: 200, data: [] }))
    renderDetail()
    await userEvent.click(await screen.findByRole('button', { name: '첫 태스크 추가' }))
    expect(screen.getByRole('dialog', { name: '새 태스크' })).toBeInTheDocument()
  })

  it('creates a task, refetches the list and the project, and goes to the task page', async () => {
    let created = false
    const handler = api(() => ({
      status: 200,
      data: created ? [task(1, '할 일 추가 기능')] : [],
    }))
    const calls = mockApiClient((request) => {
      if (request.method === 'post') created = true
      return handler(request)
    })
    const { router } = renderDetail()
    await userEvent.click(await screen.findByRole('button', { name: '첫 태스크 추가' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('태스크 제목'), '할 일 추가 기능')
    await userEvent.upload(within(dialog).getByLabelText(/파일 선택/), new File(['x'], 'a.py'))
    await userEvent.click(within(dialog).getByRole('button', { name: '태스크 만들기' }))
    await userEvent.click(await within(dialog).findByRole('button', { name: '태스크 보기' }))

    expect(router.state.location.pathname).toBe(`/tasks/${RAW_UPLOAD_RESULT.id}`)
    expect(calls.filter((c) => c.method === 'get' && c.url === TASKS_URL)).toHaveLength(2)
    expect(calls.filter((c) => c.method === 'get' && c.url === PROJECT_URL)).toHaveLength(2)
  })
})
