import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { POLL_INTERVAL_MS, useLearningDocument } from '../../src/hooks/useLearningDocument'
import { createQueryClient } from '../../src/lib/queryClient'
import { RAW_CONTENT } from '../helpers/documents'
import { errorReply, mockApiClient, restoreApiClient, type Reply } from '../helpers/http'

const TASK_ID = 't-1'

function status(value: string, extra: Record<string, unknown> = {}): Reply {
  return {
    status: 200,
    data: {
      task_id: TASK_ID,
      status: value,
      started_at: null,
      completed_at: null,
      estimated_seconds_remaining: null,
      error: null,
      ...extra,
    },
  }
}

const DOCUMENT_REPLY: Reply = {
  status: 200,
  data: { task_id: TASK_ID, status: 'completed', completed_at: null, content: RAW_CONTENT },
}

function setup() {
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return renderHook(() => useLearningDocument(TASK_ID), { wrapper })
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

afterEach(() => {
  vi.useRealTimers()
  restoreApiClient()
})

describe('useLearningDocument', () => {
  it('polls the status every 3 seconds while the document is generating', async () => {
    expect(POLL_INTERVAL_MS).toBe(3000)
    const calls = mockApiClient(() => status('in_progress'))
    setup()
    await waitFor(() => expect(calls).toHaveLength(1))

    await act(() => vi.advanceTimersByTimeAsync(3000))
    await waitFor(() => expect(calls).toHaveLength(2))
    await act(() => vi.advanceTimersByTimeAsync(3000))
    await waitFor(() => expect(calls).toHaveLength(3))
    expect(calls.every((call) => call.url === '/tasks/t-1/document/status')).toBe(true)
  })

  it('keeps polling while pending', async () => {
    const calls = mockApiClient(() => status('pending'))
    setup()
    await waitFor(() => expect(calls).toHaveLength(1))
    await act(() => vi.advanceTimersByTimeAsync(3000))
    await waitFor(() => expect(calls).toHaveLength(2))
  })

  it('stops polling and fetches the document once when it completes', async () => {
    let statusCalls = 0
    const calls = mockApiClient(({ url }) => {
      if (url.endsWith('/document/status')) {
        statusCalls += 1
        return status(statusCalls === 1 ? 'in_progress' : 'completed')
      }
      return DOCUMENT_REPLY
    })
    const { result } = setup()
    await waitFor(() => expect(statusCalls).toBe(1))
    expect(result.current.document.data).toBeUndefined()

    await act(() => vi.advanceTimersByTimeAsync(3000))
    await waitFor(() => expect(result.current.document.data).toBeDefined())
    expect(result.current.document.data?.content.chapter1.summary).toBe(
      RAW_CONTENT.chapter1.summary,
    )

    await act(() => vi.advanceTimersByTimeAsync(10_000))
    expect(statusCalls).toBe(2)
    expect(calls.filter((call) => call.url === '/tasks/t-1/document')).toHaveLength(1)
  })

  it('stops polling on failed and does not fetch the document', async () => {
    const calls = mockApiClient(() =>
      status('failed', { error: { reason: 'timeout', message: '시간 초과' } }),
    )
    const { result } = setup()
    await waitFor(() => expect(result.current.status.data?.status).toBe('failed'))
    await act(() => vi.advanceTimersByTimeAsync(10_000))
    expect(calls).toHaveLength(1)
  })

  it('exposes a status error (for example 404 document_not_found)', async () => {
    mockApiClient(() => errorReply(404, 'document_not_found', '이 태스크의 학습 문서가 없습니다.'))
    const { result } = setup()
    await waitFor(() => expect(result.current.status.isError).toBe(true))
    expect(result.current.status.error?.message).toBe('이 태스크의 학습 문서가 없습니다.')
  })

  it('regenerate: posts, shows pending and resumes polling', async () => {
    let regenerated = false
    const calls = mockApiClient(({ method }) => {
      if (method === 'post') {
        regenerated = true
        return { ...status('pending'), status: 202 }
      }
      return regenerated ? status('in_progress') : status('failed')
    })
    const { result } = setup()
    await waitFor(() => expect(result.current.status.data?.status).toBe('failed'))

    act(() => result.current.regenerate.mutate())
    await waitFor(() => expect(result.current.status.data?.status).toBe('pending'))
    expect(calls.some((call) => call.method === 'post')).toBe(true)

    const before = calls.length
    await act(() => vi.advanceTimersByTimeAsync(3000))
    await waitFor(() => expect(calls.length).toBeGreaterThan(before))
    await waitFor(() => expect(result.current.status.data?.status).toBe('in_progress'))
  })

  it('regenerate: exposes the error of a refused request', async () => {
    mockApiClient(({ method }) =>
      method === 'post'
        ? errorReply(409, 'document_not_failed', '실패한 학습 문서만 다시 만들 수 있습니다.')
        : status('failed'),
    )
    const { result } = setup()
    await waitFor(() => expect(result.current.status.data?.status).toBe('failed'))
    act(() => result.current.regenerate.mutate())
    await waitFor(() => expect(result.current.regenerate.isError).toBe(true))
    expect(result.current.regenerate.error?.message).toBe(
      '실패한 학습 문서만 다시 만들 수 있습니다.',
    )
  })
})
