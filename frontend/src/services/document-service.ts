import type { AxiosInstance } from 'axios'
import { apiClient } from './api-client'
import type { DocumentContent } from './document-types'

export type DocumentStatusValue = 'pending' | 'in_progress' | 'completed' | 'failed'

export interface DocumentStatus {
  taskId: string
  status: DocumentStatusValue
  startedAt: string | null
  completedAt: string | null
  /** Only while pending or in progress. */
  estimatedSecondsRemaining: number | null
  /** Only when failed; the message is Korean and ready to show. */
  error: { reason: string; message: string } | null
}

export interface LearningDocument {
  taskId: string
  completedAt: string | null
  content: DocumentContent
}

type Raw = Record<string, unknown>

const STATUS_VALUES: readonly string[] = ['pending', 'in_progress', 'completed', 'failed']
const UNEXPECTED_RESPONSE = '서버 응답을 이해할 수 없습니다. 잠시 후 다시 시도하세요.'

const isRecord = (value: unknown): value is Raw =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
const record = (value: unknown): Raw => (isRecord(value) ? value : {})
const list = (value: unknown): Raw[] => (Array.isArray(value) ? value.map(record) : [])
const text = (value: unknown): string => (typeof value === 'string' ? value : '')
const whole = (value: unknown): number => (typeof value === 'number' ? value : 0)
const textOrNull = (value: unknown): string | null => (typeof value === 'string' ? value : null)

/** The AI may send a list where the schema asks for text; keep it readable. */
const textOrJoined = (value: unknown): string =>
  Array.isArray(value) ? value.filter((v) => typeof v === 'string').join(', ') : text(value)

/**
 * Maps the stored document JSON to camelCase. Missing parts become empty
 * text or lists, so a slightly wrong document still shows what it has.
 */
export function toDocumentContent(raw: unknown): DocumentContent {
  const content = record(raw)
  const chapter = (key: string) => record(content[key])
  const [c1, c2, c3, c4, c5, c6, c7] = [1, 2, 3, 4, 5, 6, 7].map((n) => chapter(`chapter${n}`))
  return {
    chapter1: { title: text(c1.title), summary: text(c1.summary) },
    chapter2: {
      title: text(c2.title),
      concepts: list(c2.concepts).map((concept) => ({
        name: text(concept.name),
        explanation: text(concept.explanation),
        analogy: text(concept.analogy),
        example: text(concept.example),
        useCases: textOrJoined(concept.use_cases),
      })),
    },
    chapter3: {
      title: text(c3.title),
      flowchart: text(c3.flowchart),
      fileBreakdown: list(c3.file_breakdown).map((file) => ({
        filePath: text(file.file_path),
        role: text(file.role),
      })),
    },
    chapter4: {
      title: text(c4.title),
      explanations: list(c4.explanations).map((item) => ({
        filePath: text(item.file_path),
        lineStart: whole(item.line_start),
        lineEnd: whole(item.line_end),
        code: text(item.code),
        whatItDoes: text(item.what_it_does),
        syntaxBreakdown: text(item.syntax_breakdown),
        analogy: text(item.analogy),
        alternativeExample: text(item.alternative_example),
        notes: text(item.notes),
      })),
    },
    chapter5: {
      title: text(c5.title),
      steps: list(c5.steps).map((step) => ({
        step: whole(step.step),
        description: text(step.description),
        dataState: text(step.data_state),
      })),
    },
    chapter6: {
      title: text(c6.title),
      concepts: list(c6.concepts).map((concept) => ({
        name: text(concept.name),
        whatItIs: text(concept.what_it_is),
        whyUsed: text(concept.why_used),
        whereApplied: text(concept.where_applied),
      })),
    },
    chapter7: {
      title: text(c7.title),
      mistakes: list(c7.mistakes).map((mistake) => ({
        wrong: text(mistake.wrong),
        right: text(mistake.right),
        why: text(mistake.why),
        fix: text(mistake.fix),
      })),
    },
  }
}

function toStatus(body: unknown): DocumentStatus {
  if (!isRecord(body) || !STATUS_VALUES.includes(body.status as string)) {
    throw new Error(UNEXPECTED_RESPONSE)
  }
  const error = record(body.error)
  return {
    taskId: text(body.task_id),
    status: body.status as DocumentStatusValue,
    startedAt: textOrNull(body.started_at),
    completedAt: textOrNull(body.completed_at),
    estimatedSecondsRemaining:
      typeof body.estimated_seconds_remaining === 'number'
        ? body.estimated_seconds_remaining
        : null,
    error: isRecord(body.error)
      ? { reason: text(error.reason), message: text(error.message) }
      : null,
  }
}

const documentUrl = (taskId: string) => `/tasks/${encodeURIComponent(taskId)}/document`

export function createDocumentService(client: AxiosInstance) {
  return {
    getStatus: async (taskId: string): Promise<DocumentStatus> =>
      toStatus((await client.get<unknown>(`${documentUrl(taskId)}/status`)).data),
    getDocument: async (taskId: string): Promise<LearningDocument> => {
      const { data } = await client.get<unknown>(documentUrl(taskId))
      if (!isRecord(data) || !isRecord(data.content)) throw new Error(UNEXPECTED_RESPONSE)
      return {
        taskId: text(data.task_id),
        completedAt: textOrNull(data.completed_at),
        content: toDocumentContent(data.content),
      }
    },
    /** Starts generation again after a failure; answers with the pending status. */
    regenerate: async (taskId: string): Promise<DocumentStatus> =>
      toStatus((await client.post<unknown>(`${documentUrl(taskId)}/regenerate`)).data),
  }
}

export const documentService = createDocumentService(apiClient)
