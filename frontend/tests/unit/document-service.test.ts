import { afterEach, describe, expect, it } from 'vitest'
import { ApiError } from '../../src/services/api-client'
import { documentService, toDocumentContent } from '../../src/services/document-service'
import evenOddDocument from '../fixtures/even-odd-document.json'
import { APP_CONTENT, RAW_CONTENT } from '../helpers/documents'
import { errorReply, mockApiClient, restoreApiClient } from '../helpers/http'
import { RAW_TASK } from '../helpers/tasks'

afterEach(() => {
  restoreApiClient()
})

const TASK_ID = 't-1'

const RAW_STATUS = {
  task_id: TASK_ID,
  status: 'in_progress',
  started_at: '2026-11-18T01:00:00+00:00',
  completed_at: null,
  estimated_seconds_remaining: 95,
  error: null,
}

const APP_STATUS = {
  taskId: TASK_ID,
  status: 'in_progress',
  startedAt: '2026-11-18T01:00:00+00:00',
  completedAt: null,
  estimatedSecondsRemaining: 95,
  error: null,
}

describe('toDocumentContent', () => {
  it('maps snake_case chapter fields to camelCase', () => {
    expect(toDocumentContent(RAW_CONTENT)).toEqual(APP_CONTENT)
  })

  it('maps a real generated document with all 7 chapters', () => {
    const content = toDocumentContent(evenOddDocument)
    expect(content.chapter1.title).toBe('이 코드가 하는 일')
    expect(content.chapter4.explanations.length).toBeGreaterThan(0)
    expect(content.chapter4.explanations[0]).toMatchObject({
      filePath: 'even_odd.py',
      lineStart: 1,
      lineEnd: 2,
    })
    expect(content.chapter7.mistakes.length).toBeGreaterThanOrEqual(3)
  })

  it('joins use_cases when it arrives as a list', () => {
    const raw = structuredClone(RAW_CONTENT) as unknown as {
      chapter2: { concepts: { use_cases: unknown }[] }
    }
    raw.chapter2.concepts[0].use_cases = ['반복', '재사용']
    expect(toDocumentContent(raw).chapter2.concepts[0].useCases).toBe('반복, 재사용')
  })

  it('treats missing lists and text as empty instead of failing', () => {
    const content = toDocumentContent({})
    expect(content.chapter2.concepts).toEqual([])
    expect(content.chapter4.explanations).toEqual([])
    expect(content.chapter1.summary).toBe('')
    expect(content.chapter3.flowchart).toBe('')
  })
})

describe('documentService', () => {
  it('getStatus: GET /tasks/{id}/document/status and maps the status', async () => {
    const calls = mockApiClient(() => ({ status: 200, data: RAW_STATUS }))
    expect(await documentService.getStatus(TASK_ID)).toEqual(APP_STATUS)
    expect(calls[0]).toMatchObject({ method: 'get', url: '/tasks/t-1/document/status' })
  })

  it('getStatus: maps the error of a failed document', async () => {
    mockApiClient(() => ({
      status: 200,
      data: {
        ...RAW_STATUS,
        status: 'failed',
        estimated_seconds_remaining: null,
        error: { reason: 'timeout', message: '시간이 너무 오래 걸렸습니다.' },
      },
    }))
    const status = await documentService.getStatus(TASK_ID)
    expect(status.status).toBe('failed')
    expect(status.error).toEqual({ reason: 'timeout', message: '시간이 너무 오래 걸렸습니다.' })
  })

  it('getStatus: rejects a response that is not a status object', async () => {
    mockApiClient(() => ({ status: 200, data: RAW_TASK }))
    await expect(documentService.getStatus(TASK_ID)).rejects.toThrow()
  })

  it('getDocument: GET /tasks/{id}/document and maps the content', async () => {
    const calls = mockApiClient(() => ({
      status: 200,
      data: {
        task_id: TASK_ID,
        status: 'completed',
        completed_at: '2026-11-18T01:02:00+00:00',
        content: RAW_CONTENT,
      },
    }))
    expect(await documentService.getDocument(TASK_ID)).toEqual({
      taskId: TASK_ID,
      completedAt: '2026-11-18T01:02:00+00:00',
      content: APP_CONTENT,
    })
    expect(calls[0]).toMatchObject({ method: 'get', url: '/tasks/t-1/document' })
  })

  it('getDocument: rejects a response without content', async () => {
    mockApiClient(() => ({ status: 200, data: RAW_TASK }))
    await expect(documentService.getDocument(TASK_ID)).rejects.toThrow()
  })

  it('getDocument: passes the 409 document_not_ready error on', async () => {
    mockApiClient(() =>
      errorReply(409, 'document_not_ready', '학습 문서가 아직 준비되지 않았습니다.', {
        status: 'in_progress',
      }),
    )
    const error = await documentService.getDocument(TASK_ID).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe('document_not_ready')
  })

  it('regenerate: POST /tasks/{id}/document/regenerate and returns the pending status', async () => {
    const calls = mockApiClient(() => ({
      status: 202,
      data: { ...RAW_STATUS, status: 'pending', started_at: null, estimated_seconds_remaining: 60 },
    }))
    const status = await documentService.regenerate(TASK_ID)
    expect(calls[0]).toMatchObject({ method: 'post', url: '/tasks/t-1/document/regenerate' })
    expect(status).toMatchObject({
      status: 'pending',
      startedAt: null,
      estimatedSecondsRemaining: 60,
    })
  })

  it('regenerate: passes the 409 document_not_failed error on', async () => {
    mockApiClient(() =>
      errorReply(409, 'document_not_failed', '실패한 학습 문서만 다시 만들 수 있습니다.'),
    )
    await expect(documentService.regenerate(TASK_ID)).rejects.toMatchObject({
      code: 'document_not_failed',
    })
  })
})
