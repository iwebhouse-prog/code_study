import { afterEach, describe, expect, it } from 'vitest'
import { ApiError } from '../../src/services/api-client'
import { taskService, toTask } from '../../src/services/task-service'
import { errorReply, mockApiClient, restoreApiClient } from '../helpers/http'
import { APP_TASK, RAW_TASK, RAW_UPLOAD_RESULT } from '../helpers/tasks'

afterEach(() => {
  restoreApiClient()
})

const PROJECT_ID = 'p-1'

describe('toTask', () => {
  it('maps snake_case fields to camelCase', () => {
    expect(toTask(RAW_TASK)).toEqual(APP_TASK)
  })

  it('keeps null description, language and complexity', () => {
    const task = toTask({
      ...RAW_TASK,
      description: null,
      code: { ...RAW_TASK.code, detected_language: null, complexity_level: null },
    })
    expect(task.description).toBeNull()
    expect(task.code?.detectedLanguage).toBeNull()
    expect(task.code?.complexityLevel).toBeNull()
  })

  it('keeps a missing code summary as null', () => {
    expect(toTask({ ...RAW_TASK, code: null }).code).toBeNull()
  })
})

describe('taskService', () => {
  it('list: GET /projects/{id}/tasks and maps every task', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: [RAW_TASK] }))
    expect(await taskService.list(PROJECT_ID)).toEqual([APP_TASK])
    expect(calls[0]).toMatchObject({ method: 'get', url: '/projects/p-1/tasks' })
  })

  it('get: GET /tasks/{id}', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_TASK }))
    expect(await taskService.get('t-1')).toEqual(APP_TASK)
    expect(calls[0]).toMatchObject({ method: 'get', url: '/tasks/t-1' })
  })

  it('update: PATCH sends only the given fields, null clears the description', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_TASK }))
    await taskService.update('t-1', { description: null })
    expect(calls[0]).toMatchObject({
      method: 'patch',
      url: '/tasks/t-1',
      body: { description: null },
    })
  })

  it('remove: DELETE /tasks/{id}', async () => {
    const calls = mockApiClient(() => ({ status: 204 }))
    await taskService.remove('t-1')
    expect(calls[0]).toMatchObject({ method: 'delete', url: '/tasks/t-1' })
  })

  it('getCode: GET /tasks/{id}/code and maps the files', async () => {
    const calls = mockApiClient(() => ({
      status: 200,
      data: {
        task_id: 't-1',
        detected_language: 'javascript',
        files: [
          {
            id: 'f-1',
            file_name: 'App.jsx',
            file_path: 'src/App.jsx',
            file_extension: '.jsx',
            file_size_bytes: 12,
            language: 'javascript',
            content: 'x\n',
          },
        ],
      },
    }))
    expect(await taskService.getCode('t-1')).toEqual({
      taskId: 't-1',
      detectedLanguage: 'javascript',
      files: [
        {
          id: 'f-1',
          fileName: 'App.jsx',
          filePath: 'src/App.jsx',
          fileExtension: '.jsx',
          fileSizeBytes: 12,
          language: 'javascript',
          content: 'x\n',
        },
      ],
    })
    expect(calls[0]).toMatchObject({ method: 'get', url: '/tasks/t-1/code' })
  })

  it('shows the API error as ApiError', async () => {
    mockApiClient(() => errorReply(404, 'not_found', '없음'))
    await expect(taskService.get('t-1')).rejects.toBeInstanceOf(ApiError)
  })
})

describe('taskService.create', () => {
  const upload = (path: string, content = 'print(1)') => ({
    file: new File([content], path.split('/').pop() ?? path),
    path,
  })

  it('posts multipart form data with title, description, method and one files part per file', async () => {
    const calls = mockApiClient(() => ({ status: 201, data: RAW_UPLOAD_RESULT }))
    await taskService.create(PROJECT_ID, {
      title: '할 일 추가 기능',
      description: '설명',
      uploadMethod: 'file',
      files: [upload('a.py'), upload('b.js')],
    })
    expect(calls[0]).toMatchObject({ method: 'post', url: '/projects/p-1/tasks' })
    const form = calls[0].body as FormData
    expect(form).toBeInstanceOf(FormData)
    expect(form.get('title')).toBe('할 일 추가 기능')
    expect(form.get('description')).toBe('설명')
    expect(form.get('upload_method')).toBe('file')
    expect(form.getAll('files').map((f) => (f as File).name)).toEqual(['a.py', 'b.js'])
    expect(form.has('code')).toBe(false)
    expect(form.has('language')).toBe(false)
  })

  it('uses the relative path as the filename for folders', async () => {
    const calls = mockApiClient(() => ({ status: 201, data: RAW_UPLOAD_RESULT }))
    await taskService.create(PROJECT_ID, {
      title: '폴더 업로드',
      uploadMethod: 'folder',
      files: [upload('my-app/src/App.jsx')],
    })
    const form = calls[0].body as FormData
    expect(form.get('upload_method')).toBe('folder')
    expect((form.get('files') as File).name).toBe('my-app/src/App.jsx')
    expect(form.has('description')).toBe(false)
  })

  it('sends code and language for pasted code', async () => {
    const calls = mockApiClient(() => ({ status: 201, data: RAW_UPLOAD_RESULT }))
    await taskService.create(PROJECT_ID, {
      title: '붙여넣기 태스크',
      uploadMethod: 'paste',
      code: 'print(1)',
      language: 'python',
    })
    const form = calls[0].body as FormData
    expect(form.get('upload_method')).toBe('paste')
    expect(form.get('code')).toBe('print(1)')
    expect(form.get('language')).toBe('python')
    expect(form.has('files')).toBe(false)
  })

  it('maps the upload result with files and excluded paths', async () => {
    mockApiClient(() => ({ status: 201, data: RAW_UPLOAD_RESULT }))
    const result = await taskService.create(PROJECT_ID, {
      title: '할 일 추가 기능',
      uploadMethod: 'file',
      files: [upload('a.py')],
    })
    expect(result).toEqual({
      ...APP_TASK,
      files: [
        {
          id: '33333333-3333-4333-8333-333333333333',
          fileName: 'App.jsx',
          filePath: 'src/App.jsx',
          fileExtension: '.jsx',
          fileSizeBytes: 1240,
          language: 'javascript',
        },
      ],
      excludedPaths: ['node_modules/react/index.js'],
    })
  })

  it('rejects with the API error and its suggestion', async () => {
    mockApiClient(() => ({
      status: 400,
      data: {
        error: 'binary_file',
        message: '소스 코드 텍스트 파일만 업로드할 수 있습니다.',
        suggestion: '텍스트로 저장하세요.',
      },
    }))
    const error = await taskService
      .create(PROJECT_ID, {
        title: '오류 태스크',
        uploadMethod: 'paste',
        code: 'x',
        language: 'text',
      })
      .catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).suggestion).toBe('텍스트로 저장하세요.')
  })
})
