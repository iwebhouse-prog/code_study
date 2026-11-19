import { QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DocumentViewer } from '../../src/components/document/DocumentViewer'
import { createQueryClient } from '../../src/lib/queryClient'
import { DOC_TASK_ID, RAW_CODE, RAW_DOCUMENT, rawStatus } from '../helpers/documents'
import { errorReply, mockApiClient, restoreApiClient, type Handler } from '../helpers/http'

vi.mock('../../src/components/document/LazyCodeEditor', () => ({
  LazyCodeEditor: () => <div data-testid="editor" />,
}))

const STATUS_URL = `/tasks/${DOC_TASK_ID}/document/status`
const REGENERATE_URL = `/tasks/${DOC_TASK_ID}/document/regenerate`

function renderViewer() {
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={queryClient}>
      <DocumentViewer taskId={DOC_TASK_ID} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  HTMLElement.prototype.scrollTo = vi.fn() as unknown as typeof HTMLElement.prototype.scrollTo
})

afterEach(() => {
  vi.useRealTimers()
  restoreApiClient()
})

describe('DocumentViewer while checking the status', () => {
  it('shows a status message first', () => {
    mockApiClient(() => new Promise(() => undefined))
    renderViewer()
    expect(screen.getByRole('status')).toHaveTextContent('학습 문서 상태를 확인하는 중입니다…')
  })
})

describe('DocumentViewer generating state (T107)', () => {
  it.each(['pending', 'in_progress'])('shows the generating texts when %s', async (status) => {
    mockApiClient(() => ({
      status: 200,
      data: rawStatus(status, { estimated_seconds_remaining: 95 }),
    }))
    renderViewer()
    await screen.findByText('학습 문서 생성 중...')
    const region = screen.getByRole('status')
    expect(region).toHaveTextContent('학습 문서 생성 중...')
    expect(region).toHaveTextContent('AI가 코드를 분석하고 초보자용 설명을 작성하고 있습니다.')
  })

  it('has a labelled progress indicator inside the live region', async () => {
    mockApiClient(() => ({ status: 200, data: rawStatus('in_progress') }))
    renderViewer()
    const bar = await screen.findByRole('progressbar', { name: '학습 문서 생성 진행 상황' })
    const region = screen.getByRole('status')
    expect(region).toContainElement(bar)
    expect(region).toHaveAttribute('aria-live', 'polite')
  })

  it.each([
    [95, '약 2분 남음'],
    [120, '약 2분 남음'],
    [121, '약 3분 남음'],
    [60, '약 1분 남음'],
    [59, '1분 이내'],
    [5, '1분 이내'],
  ])('shows %i seconds as "%s"', async (seconds, text) => {
    mockApiClient(() => ({
      status: 200,
      data: rawStatus('in_progress', { estimated_seconds_remaining: seconds }),
    }))
    renderViewer()
    expect(await screen.findByText(text)).toBeInTheDocument()
  })

  it('shows no estimate when the server gives none', async () => {
    mockApiClient(() => ({ status: 200, data: rawStatus('pending') }))
    renderViewer()
    await screen.findByText('학습 문서 생성 중...')
    expect(screen.queryByText(/남음|1분 이내/)).not.toBeInTheDocument()
  })

  it('does not load the code or the document yet', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: rawStatus('in_progress') }))
    renderViewer()
    await screen.findByText('학습 문서 생성 중...')
    expect(calls.map((call) => call.url)).toEqual([STATUS_URL])
  })

  it('switches to the document by itself once the status turns completed', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let polls = 0
    const handler: Handler = ({ url }) => {
      if (url === STATUS_URL) {
        polls += 1
        return { status: 200, data: rawStatus(polls === 1 ? 'in_progress' : 'completed') }
      }
      if (url.endsWith('/document')) return { status: 200, data: RAW_DOCUMENT }
      return { status: 200, data: RAW_CODE }
    }
    mockApiClient(handler)
    renderViewer()
    await screen.findByText('학습 문서 생성 중...')

    await act(() => vi.advanceTimersByTimeAsync(3000))
    expect(await screen.findByRole('region', { name: '학습 문서 설명' })).toBeInTheDocument()
    expect(screen.queryByText('학습 문서 생성 중...')).not.toBeInTheDocument()
  })
})

describe('DocumentViewer failed state (T107)', () => {
  const FAILED = rawStatus('failed', {
    error: { reason: 'ai_unavailable', message: 'AI 서비스가 잠시 응답하지 않았습니다.' },
  })

  it('shows the error message from the server and a regenerate button', async () => {
    mockApiClient(() => ({ status: 200, data: FAILED }))
    renderViewer()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'AI 서비스가 잠시 응답하지 않았습니다.',
    )
    expect(screen.getByRole('button', { name: '다시 만들기' })).toBeEnabled()
  })

  it('has a fallback text when a failed status carries no error', async () => {
    mockApiClient(() => ({ status: 200, data: { ...FAILED, error: null } }))
    renderViewer()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '학습 문서를 만드는 중 오류가 발생했습니다. 다시 시도하세요.',
    )
  })

  it('regenerates on click and goes back to the generating state', async () => {
    let regenerated = false
    const calls = mockApiClient(({ method }) => {
      if (method === 'post') {
        regenerated = true
        return { status: 202, data: rawStatus('pending', { estimated_seconds_remaining: 60 }) }
      }
      return {
        status: 200,
        data: regenerated ? rawStatus('pending', { estimated_seconds_remaining: 60 }) : FAILED,
      }
    })
    renderViewer()
    await userEvent.click(await screen.findByRole('button', { name: '다시 만들기' }))
    expect(await screen.findByText('학습 문서 생성 중...')).toBeInTheDocument()
    expect(calls.find((call) => call.method === 'post')?.url).toBe(REGENERATE_URL)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('locks the button while the request is running', async () => {
    mockApiClient(({ method }) =>
      method === 'post' ? new Promise(() => undefined) : { status: 200, data: FAILED },
    )
    renderViewer()
    await userEvent.click(await screen.findByRole('button', { name: '다시 만들기' }))
    expect(screen.getByRole('button', { name: '다시 만드는 중…' })).toBeDisabled()
  })

  it('shows why regenerating was refused and keeps the button', async () => {
    mockApiClient(({ method }) =>
      method === 'post'
        ? errorReply(409, 'document_not_failed', '실패한 학습 문서만 다시 만들 수 있습니다.')
        : { status: 200, data: FAILED },
    )
    renderViewer()
    await userEvent.click(await screen.findByRole('button', { name: '다시 만들기' }))
    expect(await screen.findByText('실패한 학습 문서만 다시 만들 수 있습니다.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '다시 만들기' })).toBeEnabled()
  })
})
