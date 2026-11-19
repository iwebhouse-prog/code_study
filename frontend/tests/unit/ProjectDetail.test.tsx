import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
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

const PROJECT_URL = `/projects/${RAW_PROJECT.id}`

function renderDetail() {
  const queryClient = createQueryClient()
  // No automatic retries: the error state should appear right away.
  queryClient.setDefaultOptions({ queries: { retry: false } })
  const router = createMemoryRouter(routes, { initialEntries: [PROJECT_URL] })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { router, queryClient }
}

const ok: Handler = ({ url }) =>
  url === '/projects' ? { status: 200, data: [] } : { status: 200, data: RAW_PROJECT }

/** Answers like `ok`, except for one HTTP method. */
function okExcept(method: string, reply: ReturnType<Handler>): Handler {
  return (request) => (request.method === method ? reply : ok(request))
}

beforeEach(() => {
  useAuthStore.getState().setUser(APP_USER)
  useToastStore.setState({ toasts: [] })
})

afterEach(() => {
  restoreApiClient()
})

describe('ProjectDetail: view', () => {
  it('shows a loading message first', () => {
    mockApiClient(() => new Promise(() => undefined))
    renderDetail()
    expect(screen.getByText('프로젝트를 불러오는 중입니다…')).toBeInTheDocument()
  })

  it('loads the project named in the URL and shows its information', async () => {
    const calls = mockApiClient(ok)
    renderDetail()
    expect(
      await screen.findByRole('heading', { level: 1, name: 'My Todo App' }),
    ).toBeInTheDocument()
    expect(calls[0]).toMatchObject({ method: 'get', url: PROJECT_URL })
    expect(screen.getByText('할 일 앱 만들기')).toBeInTheDocument()
    expect(screen.getByText('완료 2/5 태스크')).toBeInTheDocument()
    expect(screen.getByText('만든 날짜: 2026년 11월 9일')).toBeInTheDocument()
    expect(screen.getByText('마지막 활동: 2026년 11월 10일')).toBeInTheDocument()
  })

  it('says so when the project has no description', async () => {
    mockApiClient(() => ({ status: 200, data: { ...RAW_PROJECT, description: null } }))
    renderDetail()
    expect(await screen.findByText('설명이 없습니다.')).toBeInTheDocument()
  })

  it('has a section for the task timeline', async () => {
    mockApiClient((request) =>
      request.url === `${PROJECT_URL}/tasks` ? { status: 200, data: [] } : ok(request),
    )
    renderDetail()
    expect(await screen.findByRole('heading', { level: 2, name: '태스크' })).toBeInTheDocument()
    expect(await screen.findByText('아직 태스크가 없습니다')).toBeInTheDocument()
  })

  it('links back to the dashboard', async () => {
    mockApiClient(ok)
    const { router } = renderDetail()
    await userEvent.click(await screen.findByRole('link', { name: '내 프로젝트로 돌아가기' }))
    expect(router.state.location.pathname).toBe('/')
  })

  it.each([
    [403, 'forbidden', '이 프로젝트에 접근할 권한이 없습니다.'],
    [404, 'not_found', '요청한 프로젝트를 찾을 수 없습니다.'],
  ])('shows the API message and a way back on %i', async (status, code, message) => {
    mockApiClient(() => errorReply(status, code, message))
    const { router } = renderDetail()
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: '내 프로젝트로 돌아가기' }))
    expect(router.state.location.pathname).toBe('/')
  })
})

describe('ProjectDetail: edit', () => {
  async function openEdit() {
    await userEvent.click(await screen.findByRole('button', { name: '수정' }))
    return screen.getByRole('dialog', { name: '프로젝트 수정' })
  }

  it('starts with the current values', async () => {
    mockApiClient(ok)
    renderDetail()
    const dialog = await openEdit()
    expect(within(dialog).getByLabelText('프로젝트 제목')).toHaveValue('My Todo App')
    expect(within(dialog).getByLabelText('설명 (선택)')).toHaveValue('할 일 앱 만들기')
  })

  it('sends only the changed title, shows the update and a toast', async () => {
    const calls = mockApiClient(
      okExcept('patch', { status: 200, data: { ...RAW_PROJECT, title: '새 제목' } }),
    )
    renderDetail()
    const dialog = await openEdit()
    const title = within(dialog).getByLabelText('프로젝트 제목')
    await userEvent.clear(title)
    await userEvent.type(title, ' 새 제목 ')
    await userEvent.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('heading', { level: 1, name: '새 제목' })).toBeInTheDocument()
    const patch = calls.find((c) => c.method === 'patch')
    expect(patch).toMatchObject({ url: PROJECT_URL, body: { title: '새 제목' } })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('프로젝트가 수정되었습니다.')
  })

  it('sends description null when the description is cleared', async () => {
    const calls = mockApiClient(
      okExcept('patch', { status: 200, data: { ...RAW_PROJECT, description: null } }),
    )
    renderDetail()
    const dialog = await openEdit()
    await userEvent.clear(within(dialog).getByLabelText('설명 (선택)'))
    await userEvent.click(within(dialog).getByRole('button', { name: '저장' }))
    expect(await screen.findByText('설명이 없습니다.')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'patch')?.body).toEqual({ description: null })
  })

  it('sends a changed description', async () => {
    const calls = mockApiClient(
      okExcept('patch', { status: 200, data: { ...RAW_PROJECT, description: '새 설명' } }),
    )
    renderDetail()
    const dialog = await openEdit()
    const description = within(dialog).getByLabelText('설명 (선택)')
    await userEvent.clear(description)
    await userEvent.type(description, '새 설명')
    await userEvent.click(within(dialog).getByRole('button', { name: '저장' }))
    expect(await screen.findByText('새 설명')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'patch')?.body).toEqual({ description: '새 설명' })
  })

  it('does not call the server when nothing changed', async () => {
    const calls = mockApiClient(ok)
    renderDetail()
    const dialog = await openEdit()
    await userEvent.click(within(dialog).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.some((c) => c.method === 'patch')).toBe(false)
  })

  it('checks the title before saving', async () => {
    const calls = mockApiClient(ok)
    renderDetail()
    const dialog = await openEdit()
    await userEvent.clear(within(dialog).getByLabelText('프로젝트 제목'))
    await userEvent.click(within(dialog).getByRole('button', { name: '저장' }))
    expect(
      await within(dialog).findByText('프로젝트 제목은 최소 1자 이상이어야 합니다.'),
    ).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'patch')).toBe(false)
  })

  it('shows the server error and keeps the dialog open', async () => {
    mockApiClient(
      okExcept(
        'patch',
        errorReply(400, 'validation_error', '입력값 오류', {
          fields: [{ field: 'title', message: '제목이 올바르지 않습니다.' }],
        }),
      ),
    )
    renderDetail()
    const dialog = await openEdit()
    await userEvent.type(within(dialog).getByLabelText('프로젝트 제목'), '!')
    await userEvent.click(within(dialog).getByRole('button', { name: '저장' }))
    expect(await within(dialog).findByText('제목이 올바르지 않습니다.')).toBeInTheDocument()
  })

  it('refreshes the project list after saving', async () => {
    mockApiClient(okExcept('patch', { status: 200, data: { ...RAW_PROJECT, title: 'B' } }))
    const { queryClient } = renderDetail()
    queryClient.setQueryData(['projects'], [])
    const dialog = await openEdit()
    await userEvent.type(within(dialog).getByLabelText('프로젝트 제목'), 'B')
    await userEvent.click(within(dialog).getByRole('button', { name: '저장' }))
    await screen.findByText('프로젝트가 수정되었습니다.')
    expect(queryClient.getQueryState(['projects'])?.isInvalidated).toBe(true)
  })
})

describe('ProjectDetail: delete', () => {
  async function openConfirm() {
    await userEvent.click(await screen.findByRole('button', { name: '삭제' }))
    return screen.getByRole('alertdialog', { name: '프로젝트를 삭제할까요?' })
  }

  it('asks for confirmation inside the page and can be cancelled', async () => {
    const calls = mockApiClient(ok)
    renderDetail()
    const dialog = await openConfirm()
    expect(dialog).toHaveTextContent('My Todo App')
    await userEvent.click(within(dialog).getByRole('button', { name: '취소' }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(calls.some((c) => c.method === 'delete')).toBe(false)
  })

  it('deletes, shows a toast and goes to the dashboard', async () => {
    const calls = mockApiClient(okExcept('delete', { status: 204 }))
    const { router, queryClient } = renderDetail()
    const dialog = await openConfirm()
    await userEvent.click(within(dialog).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    expect(calls).toContainEqual(expect.objectContaining({ method: 'delete', url: PROJECT_URL }))
    expect(await screen.findByText('아직 프로젝트가 없습니다')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('프로젝트가 휴지통으로 이동되었습니다.')
    expect(queryClient.getQueryData(['projects', RAW_PROJECT.id])).toBeUndefined()
  })

  it('shows the API message and stays when deleting fails', async () => {
    mockApiClient(
      okExcept('delete', errorReply(403, 'forbidden', '이 프로젝트에 접근할 권한이 없습니다.')),
    )
    const { router } = renderDetail()
    const dialog = await openConfirm()
    await userEvent.click(within(dialog).getByRole('button', { name: '삭제' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      '이 프로젝트에 접근할 권한이 없습니다.',
    )
    expect(router.state.location.pathname).toBe(PROJECT_URL)
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('disables the delete button while deleting', async () => {
    mockApiClient(okExcept('delete', new Promise<Reply>(() => undefined)))
    renderDetail()
    const dialog = await openConfirm()
    await userEvent.click(within(dialog).getByRole('button', { name: '삭제' }))
    expect(await within(dialog).findByRole('button', { name: '삭제하는 중…' })).toBeDisabled()
  })
})

describe('ProjectDetail: unexpected delete failure', () => {
  it('shows a fallback message when the failure has no API message', async () => {
    mockApiClient(({ method }) => {
      if (method === 'delete') throw new Error('boom')
      return { status: 200, data: RAW_PROJECT }
    })
    renderDetail()
    await userEvent.click(await screen.findByRole('button', { name: '삭제' }))
    const dialog = screen.getByRole('alertdialog')
    await userEvent.click(within(dialog).getByRole('button', { name: '삭제' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      '프로젝트를 삭제하지 못했습니다. 잠시 후 다시 시도하세요.',
    )
  })
})
