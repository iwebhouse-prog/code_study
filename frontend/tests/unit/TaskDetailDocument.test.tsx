import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createQueryClient } from '../../src/lib/queryClient'
import { routes } from '../../src/routes'
import { useAuthStore } from '../../src/stores/auth-store'
import { RAW_CODE, RAW_DOCUMENT, rawStatus } from '../helpers/documents'
import { APP_USER, mockApiClient, restoreApiClient } from '../helpers/http'
import { RAW_TASK } from '../helpers/tasks'

vi.mock('../../src/components/document/LazyCodeEditor', () => ({
  LazyCodeEditor: () => <div data-testid="editor" />,
}))

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
}

beforeEach(() => {
  useAuthStore.getState().setUser(APP_USER)
  HTMLElement.prototype.scrollTo = vi.fn() as unknown as typeof HTMLElement.prototype.scrollTo
})

afterEach(() => {
  restoreApiClient()
})

describe('TaskDetail document tab (T108)', () => {
  it('shows the generating state of the task document in the document tab', async () => {
    const calls = mockApiClient(({ url }) =>
      url === TASK_URL
        ? { status: 200, data: RAW_TASK }
        : { status: 200, data: rawStatus('in_progress', { estimated_seconds_remaining: 40 }) },
    )
    renderTask()
    expect(await screen.findByText('학습 문서 생성 중...')).toBeInTheDocument()
    expect(screen.getByText('1분 이내')).toBeInTheDocument()
    expect(calls.map((call) => call.url)).toContain(`${TASK_URL}/document/status`)
    expect(screen.queryByText('학습 문서는 곧 제공됩니다.')).not.toBeInTheDocument()
  })

  it('shows code and explanation for a completed document', async () => {
    mockApiClient(({ url }) => {
      if (url === TASK_URL) return { status: 200, data: RAW_TASK }
      if (url.endsWith('/document/status')) return { status: 200, data: rawStatus('completed') }
      if (url.endsWith('/document')) return { status: 200, data: RAW_DOCUMENT }
      return { status: 200, data: RAW_CODE }
    })
    renderTask()
    expect(await screen.findByRole('region', { name: '학습 문서 설명' })).toBeInTheDocument()
    expect(await screen.findByRole('region', { name: '코드' })).toBeInTheDocument()
  })

  it('does not ask for the document while another tab is open', async () => {
    mockApiClient(({ url }) =>
      url === TASK_URL
        ? { status: 200, data: RAW_TASK }
        : { status: 200, data: rawStatus('in_progress') },
    )
    renderTask()
    await screen.findByText('학습 문서 생성 중...')
    await userEvent.click(screen.getByRole('tab', { name: '연습 문제' }))
    expect(screen.queryByText('학습 문서 생성 중...')).not.toBeInTheDocument()
    expect(screen.getByText('연습 문제는 곧 제공됩니다.')).toBeInTheDocument()
  })
})
