import { QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CreateTaskModal from '../../src/components/task/CreateTaskModal'
import { createQueryClient } from '../../src/lib/queryClient'
import { useToastStore } from '../../src/stores/toast-store'
import { errorReply, mockApiClient, restoreApiClient, type Handler } from '../helpers/http'
import { RAW_UPLOAD_RESULT } from '../helpers/tasks'

const PROJECT_ID = 'p-1'
const TASKS_URL = `/projects/${PROJECT_ID}/tasks`
const created: Handler = () => ({ status: 201, data: RAW_UPLOAD_RESULT })

function renderModal() {
  const onOpenChange = vi.fn()
  const queryClient = createQueryClient()
  const router = createMemoryRouter(
    [
      {
        path: '/',
        element: <CreateTaskModal projectId={PROJECT_ID} open onOpenChange={onOpenChange} />,
      },
      { path: '/tasks/:taskId', element: <p>태스크 페이지</p> },
    ],
    { initialEntries: ['/'] },
  )
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { onOpenChange, queryClient, router }
}

beforeEach(() => {
  useToastStore.setState({ toasts: [] })
})

afterEach(() => {
  restoreApiClient()
})

const dialog = () => screen.getByRole('dialog')
const titleInput = () => screen.getByLabelText('태스크 제목')
const submit = () => screen.getByRole('button', { name: '태스크 만들기' })
const code = (name: string, content = 'print(1)') => new File([content], name)

async function typeTitle(title = '할 일 추가 기능') {
  await userEvent.type(titleInput(), title)
}

async function uploadFiles(files: File[]) {
  await userEvent.upload(screen.getByLabelText(/파일 선택/), files)
}

function pickFolder(paths: string[]) {
  const files = paths.map((path) => {
    const file = code(path.split('/').pop() ?? path)
    Object.defineProperty(file, 'webkitRelativePath', { value: path })
    return file
  })
  fireEvent.change(screen.getByLabelText(/폴더 선택/), { target: { files } })
}

function lastForm(calls: { body: unknown }[]): FormData {
  return calls[calls.length - 1].body as FormData
}

describe('CreateTaskModal: layout', () => {
  it('is a named dialog with title, description and three upload tabs', () => {
    renderModal()
    expect(screen.getByRole('dialog', { name: '새 태스크' })).toBeInTheDocument()
    expect(titleInput()).toBeRequired()
    expect(screen.getByLabelText('설명 (선택)')).not.toBeRequired()
    const tabs = screen.getAllByRole('tab').map((tab) => tab.textContent)
    expect(tabs).toEqual(['파일 업로드', '폴더 업로드', '코드 붙여넣기'])
  })

  it('starts on the file tab and switches panels', async () => {
    renderModal()
    expect(screen.getByRole('tab', { name: '파일 업로드' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByLabelText(/파일 선택/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: '폴더 업로드' }))
    expect(screen.getByLabelText(/폴더 선택/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/파일 선택/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    expect(screen.getByLabelText('붙여넣을 코드')).toBeInTheDocument()
    expect(screen.getByRole('tabpanel')).toContainElement(screen.getByLabelText('프로그래밍 언어'))
  })

  it('keeps the title when the tab changes', async () => {
    renderModal()
    await typeTitle('유지되는 제목')
    await userEvent.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    expect(titleInput()).toHaveValue('유지되는 제목')
  })

  it('cancel closes the dialog without a request', async () => {
    const calls = mockApiClient(created)
    const { onOpenChange } = renderModal()
    await userEvent.click(screen.getByRole('button', { name: '취소' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(calls).toHaveLength(0)
  })
})

describe('CreateTaskModal: creating', () => {
  it('uploads files, then shows the confirmation with every file and excluded path', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    await userEvent.type(screen.getByLabelText('설명 (선택)'), '  설명  ')
    await uploadFiles([code('a.py'), code('B.JS')])
    await userEvent.click(submit())

    const heading = await screen.findByRole('heading', { name: '업로드 완료' })
    expect(heading).toBeInTheDocument()
    expect(calls[0]).toMatchObject({ method: 'post', url: TASKS_URL })
    const form = lastForm(calls)
    expect(form.get('title')).toBe('할 일 추가 기능')
    expect(form.get('description')).toBe('설명')
    expect(form.get('upload_method')).toBe('file')
    expect(form.getAll('files').map((f) => (f as File).name)).toEqual(['a.py', 'B.JS'])

    const files = within(screen.getByRole('list', { name: '업로드한 파일' }))
    expect(files.getByText('src/App.jsx')).toBeInTheDocument()
    const excluded = within(screen.getByRole('list', { name: '제외된 파일' }))
    expect(excluded.getByText('node_modules/react/index.js')).toBeInTheDocument()
  })

  it('omits the excluded list when nothing was excluded', async () => {
    mockApiClient(() => ({ status: 201, data: { ...RAW_UPLOAD_RESULT, excluded_paths: [] } }))
    renderModal()
    await typeTitle()
    await uploadFiles([code('a.py')])
    await userEvent.click(submit())
    await screen.findByRole('heading', { name: '업로드 완료' })
    expect(screen.queryByRole('list', { name: '제외된 파일' })).not.toBeInTheDocument()
  })

  it('shows the success toast and refreshes the project and its tasks', async () => {
    mockApiClient(created)
    const { queryClient } = renderModal()
    queryClient.setQueryData(['projects', PROJECT_ID, 'tasks'], [])
    queryClient.setQueryData(['projects', PROJECT_ID], {})
    await typeTitle()
    await uploadFiles([code('a.py')])
    await userEvent.click(submit())
    await screen.findByRole('heading', { name: '업로드 완료' })
    expect(useToastStore.getState().toasts.map((t) => t.message)).toEqual([
      '태스크가 생성되었습니다.',
    ])
    expect(queryClient.getQueryState(['projects', PROJECT_ID, 'tasks'])?.isInvalidated).toBe(true)
    expect(queryClient.getQueryState(['projects', PROJECT_ID])?.isInvalidated).toBe(true)
  })

  it('"태스크 보기" closes the dialog and opens the task page', async () => {
    mockApiClient(created)
    const { router, onOpenChange } = renderModal()
    await typeTitle()
    await uploadFiles([code('a.py')])
    await userEvent.click(submit())
    await userEvent.click(await screen.findByRole('button', { name: '태스크 보기' }))
    expect(router.state.location.pathname).toBe(`/tasks/${RAW_UPLOAD_RESULT.id}`)
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('uploads a folder with relative paths and drops excluded folders', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    await userEvent.click(screen.getByRole('tab', { name: '폴더 업로드' }))
    pickFolder(['app/src/App.jsx', 'app/node_modules/x/index.js'])
    expect(screen.getByText('제외된 폴더: node_modules')).toBeInTheDocument()
    await userEvent.click(submit())
    await screen.findByRole('heading', { name: '업로드 완료' })
    const form = lastForm(calls)
    expect(form.get('upload_method')).toBe('folder')
    expect(form.getAll('files').map((f) => (f as File).name)).toEqual(['app/src/App.jsx'])
  })

  it('uploads pasted code with its language', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    await userEvent.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    await userEvent.click(screen.getByLabelText('붙여넣을 코드'))
    await userEvent.paste('print(1)')
    await userEvent.selectOptions(screen.getByLabelText('프로그래밍 언어'), 'python')
    await userEvent.click(submit())
    await screen.findByRole('heading', { name: '업로드 완료' })
    const form = lastForm(calls)
    expect(form.get('upload_method')).toBe('paste')
    expect(form.get('code')).toBe('print(1)')
    expect(form.get('language')).toBe('python')
  })

  it('disables the button while uploading', async () => {
    mockApiClient(() => new Promise(() => undefined))
    renderModal()
    await typeTitle()
    await uploadFiles([code('a.py')])
    await userEvent.click(submit())
    expect(await screen.findByRole('button', { name: '만드는 중…' })).toBeDisabled()
  })
})

describe('CreateTaskModal: checks before sending', () => {
  async function expectBlocked(message: string, calls: unknown[]) {
    expect(await within(dialog()).findByText(message)).toBeInTheDocument()
    expect(calls).toHaveLength(0)
  }

  it('rejects a title shorter than 5 characters', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle('짧음')
    await uploadFiles([code('a.py')])
    await userEvent.click(submit())
    await expectBlocked('태스크 제목은 최소 5자 이상이어야 합니다.', calls)
    expect(titleInput()).toHaveAttribute('aria-invalid', 'true')
  })

  it('counts the title after trimming', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle('  abcd  ')
    await uploadFiles([code('a.py')])
    await userEvent.click(submit())
    await expectBlocked('태스크 제목은 최소 5자 이상이어야 합니다.', calls)
  })

  it('rejects a title longer than 255 characters', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await userEvent.click(titleInput())
    await userEvent.paste('a'.repeat(256))
    await uploadFiles([code('a.py')])
    await userEvent.click(submit())
    await expectBlocked('태스크 제목은 최대 255자까지 입력할 수 있습니다.', calls)
  })

  it('rejects a description longer than 500 characters', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    await userEvent.click(screen.getByLabelText('설명 (선택)'))
    await userEvent.paste('a'.repeat(501))
    await uploadFiles([code('a.py')])
    await userEvent.click(submit())
    await expectBlocked('태스크 설명은 최대 500자까지 입력할 수 있습니다.', calls)
  })

  it('accepts a title of 5 and a description of 500 characters', async () => {
    mockApiClient(created)
    renderModal()
    await typeTitle('12345')
    await userEvent.click(screen.getByLabelText('설명 (선택)'))
    await userEvent.paste('a'.repeat(500))
    await uploadFiles([code('a.py')])
    await userEvent.click(submit())
    expect(await screen.findByRole('heading', { name: '업로드 완료' })).toBeInTheDocument()
  })

  it('asks for a file when none is chosen', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    await userEvent.click(submit())
    await expectBlocked('업로드할 파일이 없습니다.', calls)
  })

  it('rejects more than 20 files', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    await uploadFiles(Array.from({ length: 21 }, (_, i) => code(`f${i}.py`)))
    await userEvent.click(submit())
    await expectBlocked('한 번에 최대 20개 파일까지 업로드할 수 있습니다.', calls)
  })

  it('accepts exactly 20 files', async () => {
    mockApiClient(created)
    renderModal()
    await typeTitle()
    await uploadFiles(Array.from({ length: 20 }, (_, i) => code(`f${i}.py`)))
    await userEvent.click(submit())
    expect(await screen.findByRole('heading', { name: '업로드 완료' })).toBeInTheDocument()
  })

  it('rejects a total size over 10MB', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    const big = 5 * 1024 * 1024 + 1
    await uploadFiles([code('a.py', 'x'.repeat(big)), code('b.py', 'x'.repeat(big))])
    await userEvent.click(submit())
    await expectBlocked('파일 크기가 10MB를 초과합니다.', calls)
  })

  it('rejects an unsupported extension and names the file', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    await uploadFiles([code('a.py'), code('logo.png')])
    await userEvent.click(submit())
    await expectBlocked('지원하지 않는 파일 형식입니다. (logo.png)', calls)
  })

  it('checks the extension of folder files by their path', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    await userEvent.click(screen.getByRole('tab', { name: '폴더 업로드' }))
    pickFolder(['app/data.json'])
    await userEvent.click(submit())
    await expectBlocked('지원하지 않는 파일 형식입니다. (app/data.json)', calls)
  })

  it('asks for a folder when none is chosen', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    await userEvent.click(screen.getByRole('tab', { name: '폴더 업로드' }))
    await userEvent.click(submit())
    await expectBlocked('업로드할 파일이 없습니다.', calls)
  })

  it('asks for code and a language when pasting', async () => {
    const calls = mockApiClient(created)
    renderModal()
    await typeTitle()
    await userEvent.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    await userEvent.type(screen.getByLabelText('붙여넣을 코드'), '   ')
    await userEvent.click(submit())
    await expectBlocked('붙여넣을 코드를 입력하세요.', calls)
    expect(screen.getByText('프로그래밍 언어를 선택하세요.')).toBeInTheDocument()
    expect(screen.getByLabelText('붙여넣을 코드')).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('CreateTaskModal: API errors', () => {
  async function submitValid() {
    await typeTitle()
    await uploadFiles([code('a.py')])
    await userEvent.click(submit())
  }

  it('shows the API message and suggestion and keeps the dialog open', async () => {
    mockApiClient(() => ({
      status: 400,
      data: {
        error: 'unsupported_encoding',
        message: '파일의 문자 인코딩을 읽을 수 없습니다.',
        suggestion: 'UTF-8로 저장한 뒤 다시 업로드하세요.',
      },
    }))
    const { onOpenChange } = renderModal()
    await submitValid()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('파일의 문자 인코딩을 읽을 수 없습니다.')
    expect(alert).toHaveTextContent('UTF-8로 저장한 뒤 다시 업로드하세요.')
    expect(onOpenChange).not.toHaveBeenCalled()
    expect(useToastStore.getState().toasts).toHaveLength(0)
    expect(screen.getByRole('button', { name: '태스크 만들기' })).toBeEnabled()
  })

  it('shows field errors next to their fields', async () => {
    mockApiClient(() =>
      errorReply(400, 'validation_error', '입력값을 확인하세요.', {
        fields: [{ field: 'title', message: '서버: 제목 오류' }],
      }),
    )
    renderModal()
    await submitValid()
    const message = await screen.findByText('서버: 제목 오류')
    expect(titleInput().getAttribute('aria-describedby')).toBe(message.id)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows server code and language errors on the paste tab', async () => {
    mockApiClient(() =>
      errorReply(400, 'validation_error', '입력값을 확인하세요.', {
        fields: [
          { field: 'code', message: '서버: 코드 오류' },
          { field: 'language', message: '서버: 언어 오류' },
        ],
      }),
    )
    renderModal()
    await typeTitle()
    await userEvent.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    await userEvent.type(screen.getByLabelText('붙여넣을 코드'), 'x')
    await userEvent.selectOptions(screen.getByLabelText('프로그래밍 언어'), 'text')
    await userEvent.click(submit())
    expect(await screen.findByText('서버: 코드 오류')).toBeInTheDocument()
    expect(screen.getByText('서버: 언어 오류')).toBeInTheDocument()
  })

  it('shows a fallback message for an unexpected failure', async () => {
    mockApiClient(() => {
      throw new Error('boom')
    })
    renderModal()
    await submitValid()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '태스크를 만들지 못했습니다. 잠시 후 다시 시도하세요.',
    )
  })

  it('lets the user try again after a failure', async () => {
    let attempt = 0
    mockApiClient(() =>
      attempt++ === 0
        ? errorReply(500, 'internal_error', '서버 오류')
        : { status: 201, data: RAW_UPLOAD_RESULT },
    )
    renderModal()
    await submitValid()
    await screen.findByRole('alert')
    await userEvent.click(submit())
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: '업로드 완료' })).toBeInTheDocument(),
    )
  })
})
