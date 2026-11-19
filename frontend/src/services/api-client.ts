import axios, {
  type AxiosAdapter,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
  isAxiosError,
} from 'axios'

const LOCAL_API_BASE_URL = 'http://localhost:8000/api/v1'
// Generous because some calls wait on AI work; the backend's own limit is
// 30 seconds per query (DB_COMMAND_TIMEOUT).
export const DEFAULT_TIMEOUT_MS = 30_000

// Messages for failures the backend could not describe itself. Texts that
// also exist on the backend (src/api/error_messages.py) are kept identical.
export const CLIENT_ERROR_MESSAGES = {
  network_error: '서버에 연결할 수 없습니다. 인터넷 연결을 확인한 뒤 다시 시도하세요.',
  timeout: '서버 응답이 너무 늦습니다. 잠시 후 다시 시도하세요.',
  bad_request: '요청을 처리할 수 없습니다. 입력 내용을 확인한 뒤 다시 시도하세요.',
  internal_error:
    '서버 오류가 발생했습니다. 잠시 후 다시 시도하세요. 문제가 계속되면 고객지원에 문의하세요.',
} as const

/** Body of every backend error response (backend/src/api/exceptions.py). */
interface ErrorBody {
  error: string
  message: string
  details?: Record<string, unknown>
  suggestion?: string
}

interface FieldError {
  field: string
  message: string
}

/** One error type for every failed API call; `status` is undefined offline. */
export class ApiError extends Error {
  readonly status: number | undefined
  readonly code: string
  readonly details: Record<string, unknown> | undefined
  readonly suggestion: string | undefined
  readonly retryAfterSeconds: number | undefined
  /** The request that failed, so interceptors can repeat it. */
  readonly config: InternalAxiosRequestConfig | undefined

  constructor(options: {
    status?: number
    code: string
    message: string
    details?: Record<string, unknown>
    suggestion?: string
    retryAfterSeconds?: number
    config?: InternalAxiosRequestConfig
  }) {
    super(options.message)
    this.name = 'ApiError'
    this.status = options.status
    this.code = options.code
    this.details = options.details
    this.suggestion = options.suggestion
    this.retryAfterSeconds = options.retryAfterSeconds
    this.config = options.config
  }

  /** Validation messages by field name, for showing next to form inputs. */
  get fieldErrors(): Record<string, string> {
    const fields = this.details?.fields
    if (!Array.isArray(fields)) return {}
    return Object.fromEntries((fields as FieldError[]).map((f) => [f.field, f.message]))
  }
}

function isErrorBody(data: unknown): data is ErrorBody {
  if (typeof data !== 'object' || data === null) return false
  const { error, message } = data as Record<string, unknown>
  return typeof error === 'string' && typeof message === 'string'
}

function toApiError(error: unknown): unknown {
  // Cancellation (TanStack Query, unmounts) must stay as-is so callers ignore it.
  if (!isAxiosError(error) || axios.isCancel(error)) return error

  const response = error.response
  if (!response) {
    const timedOut = error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT'
    const code = timedOut ? 'timeout' : 'network_error'
    return new ApiError({ code, message: CLIENT_ERROR_MESSAGES[code] })
  }

  const retryAfter = Number(response.headers['retry-after'])
  const extra = {
    status: response.status,
    config: error.config,
    retryAfterSeconds: Number.isFinite(retryAfter) ? retryAfter : undefined,
  }
  if (isErrorBody(response.data)) {
    const { error: code, message, details, suggestion } = response.data
    return new ApiError({ ...extra, code, message, details, suggestion })
  }
  // A proxy or crash page instead of our JSON body.
  const code = response.status >= 500 ? 'internal_error' : 'bad_request'
  return new ApiError({ ...extra, code, message: CLIENT_ERROR_MESSAGES[code] })
}

export function resolveBaseUrl(env: { VITE_API_BASE_URL?: string; DEV: boolean }): string {
  const url = env.VITE_API_BASE_URL
  if (url) return url.replace(/\/+$/, '')
  if (env.DEV) return LOCAL_API_BASE_URL
  throw new Error('VITE_API_BASE_URL is not set. Add it to the production .env file.')
}

export function createApiClient(options: {
  baseURL: string
  adapter?: AxiosAdapter
}): AxiosInstance {
  const client = axios.create({
    baseURL: options.baseURL,
    adapter: options.adapter,
    // Tokens live in HTTPOnly cookies, so every request must carry cookies.
    withCredentials: true,
    timeout: DEFAULT_TIMEOUT_MS,
    headers: { Accept: 'application/json' },
  })
  client.interceptors.response.use(undefined, (error: unknown) => Promise.reject(toApiError(error)))
  return client
}

export const apiClient = createApiClient({ baseURL: resolveBaseUrl(import.meta.env) })
