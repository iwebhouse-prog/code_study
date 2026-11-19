import { QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DocumentViewer } from '../../src/components/document/DocumentViewer'
import type { MonacoEditorProps } from '../../src/components/document/MonacoEditor'
import { createQueryClient } from '../../src/lib/queryClient'
import { DOC_TASK_ID, RAW_CODE, RAW_DOCUMENT, rawStatus } from '../helpers/documents'
import { errorReply, mockApiClient, restoreApiClient, type Handler } from '../helpers/http'

// Monaco cannot run in jsdom: a stand-in shows what the editor was given and
// lets the test report a scroll.
let lastEditor: MonacoEditorProps
vi.mock('../../src/components/document/LazyCodeEditor', () => ({
  LazyCodeEditor: (props: MonacoEditorProps) => {
    lastEditor = props
    return (
      <div
        data-testid="editor"
        data-path={props.path}
        data-highlight={props.highlight ? `${props.highlight.start}-${props.highlight.end}` : ''}
      />
    )
  },
}))

const URLS = {
  status: `/tasks/${DOC_TASK_ID}/document/status`,
  document: `/tasks/${DOC_TASK_ID}/document`,
  code: `/tasks/${DOC_TASK_ID}/code`,
}

const completedApi: Handler = ({ url }) => {
  if (url === URLS.status) return { status: 200, data: rawStatus('completed') }
  if (url === URLS.document) return { status: 200, data: RAW_DOCUMENT }
  if (url === URLS.code) return { status: 200, data: RAW_CODE }
  return { status: 404, data: { error: 'not_found', message: '없음' } }
}

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
  // jsdom has no Element.scrollTo (the explanation panel scrolls itself).
  HTMLElement.prototype.scrollTo = vi.fn() as unknown as typeof HTMLElement.prototype.scrollTo
})

afterEach(() => {
  restoreApiClient()
})

describe('DocumentViewer, completed document (T105)', () => {
  it('shows the code on one side and the explanation on the other', async () => {
    mockApiClient(completedApi)
    renderViewer()
    expect(await screen.findByRole('region', { name: '코드' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '학습 문서 설명' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '챕터 이동' })).toBeInTheDocument()
  })

  it('requests status, then document and code', async () => {
    const calls = mockApiClient(completedApi)
    renderViewer()
    await screen.findByRole('region', { name: '코드' })
    const urls = calls.map((call) => call.url)
    expect(urls[0]).toBe(URLS.status)
    expect(urls).toContain(URLS.document)
    expect(urls).toContain(URLS.code)
  })

  it('lays the columns out side by side on wide screens and stacks them on narrow ones', async () => {
    mockApiClient(completedApi)
    renderViewer()
    const layout = (await screen.findByRole('region', { name: '코드' })).parentElement!
    expect(layout).toHaveClass('grid', 'grid-cols-1', 'lg:grid-cols-2')
  })

  it('shows every file of the task in the code panel', async () => {
    mockApiClient(completedApi)
    renderViewer()
    const tabs = await screen.findAllByRole('tab')
    expect(tabs.map((tab) => tab.textContent)).toEqual(['even_odd.py', 'main.py'])
  })

  it('highlights the code lines when an explanation is clicked', async () => {
    mockApiClient(completedApi)
    renderViewer()
    await userEvent.click(await screen.findByRole('button', { name: /even_odd\.py 4줄/ }))
    expect(screen.getByTestId('editor')).toHaveAttribute('data-path', 'even_odd.py')
    expect(screen.getByTestId('editor')).toHaveAttribute('data-highlight', '4-4')
    expect(screen.getByRole('button', { name: /even_odd\.py 4줄/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('opens the file of a clicked explanation that belongs to another file', async () => {
    mockApiClient(completedApi)
    renderViewer()
    await userEvent.click(await screen.findByRole('button', { name: /main\.py 1~3줄/ }))
    expect(screen.getByTestId('editor')).toHaveAttribute('data-path', 'main.py')
    expect(screen.getByTestId('editor')).toHaveAttribute('data-highlight', '1-3')
  })

  it('activates the explanation that covers the top visible line when the code scrolls', async () => {
    mockApiClient(completedApi)
    renderViewer()
    await screen.findByTestId('editor')

    act(() => lastEditor.onTopLineChange(2))
    expect(screen.getByRole('button', { name: /even_odd\.py 1~2줄/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    act(() => lastEditor.onTopLineChange(4))
    expect(screen.getByRole('button', { name: /even_odd\.py 4줄/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: /even_odd\.py 1~2줄/ })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('keeps the current explanation when the top line is covered by none', async () => {
    mockApiClient(completedApi)
    renderViewer()
    await screen.findByTestId('editor')
    act(() => lastEditor.onTopLineChange(2))
    act(() => lastEditor.onTopLineChange(3))
    expect(screen.getByRole('button', { name: /even_odd\.py 1~2줄/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('does not move the code highlight when only scrolling', async () => {
    mockApiClient(completedApi)
    renderViewer()
    await screen.findByTestId('editor')
    act(() => lastEditor.onTopLineChange(4))
    expect(screen.getByTestId('editor')).toHaveAttribute('data-highlight', '')
  })

  it('shows loading text while the document is on its way', async () => {
    mockApiClient(({ url }) =>
      url === URLS.document ? new Promise(() => undefined) : completedApi({ url } as never),
    )
    renderViewer()
    expect(await screen.findByText('학습 문서를 불러오는 중입니다…')).toBeInTheDocument()
  })

  it('shows an error when the document cannot be loaded', async () => {
    mockApiClient((request) =>
      request.url === URLS.document
        ? errorReply(404, 'document_not_found', '이 태스크의 학습 문서가 없습니다.')
        : completedApi(request),
    )
    renderViewer()
    expect(await screen.findByRole('alert')).toHaveTextContent('이 태스크의 학습 문서가 없습니다.')
  })

  it('shows an error when the code cannot be loaded, keeping the explanation', async () => {
    mockApiClient((request) =>
      request.url === URLS.code
        ? errorReply(404, 'file_missing', '코드 파일을 찾을 수 없습니다. 다시 업로드하세요.')
        : completedApi(request),
    )
    renderViewer()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('코드 파일을 찾을 수 없습니다. 다시 업로드하세요.')
    expect(screen.getByRole('region', { name: '학습 문서 설명' })).toBeInTheDocument()
    expect(within(alert).queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows the status error (for example a task without a document)', async () => {
    mockApiClient(() => errorReply(404, 'document_not_found', '이 태스크의 학습 문서가 없습니다.'))
    renderViewer()
    expect(await screen.findByRole('alert')).toHaveTextContent('이 태스크의 학습 문서가 없습니다.')
  })

  it('survives answers that are not status objects', async () => {
    mockApiClient(() => ({ status: 200, data: { id: 'x', title: 'a task' } }))
    renderViewer()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
