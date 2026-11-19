import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { describe, expect, it, vi } from 'vitest'
import { getHttpStatus, shouldRetryQuery } from '../../src/lib/queryClient'
import {
  ApiError,
  CLIENT_ERROR_MESSAGES,
  DEFAULT_TIMEOUT_MS,
  createApiClient,
  resolveBaseUrl,
} from '../../src/services/api-client'

const BASE = 'http://localhost:8000/api/v1'

function respond(status: number, data: unknown, headers: Record<string, string> = {}) {
  return (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    const response: AxiosResponse = {
      data,
      status,
      statusText: String(status),
      headers: new AxiosHeaders(headers),
      config,
    }
    if (status >= 200 && status < 300) return Promise.resolve(response)
    return Promise.reject(
      new AxiosError(`HTTP ${status}`, 'ERR_BAD_RESPONSE', config, {}, response),
    )
  }
}

function clientWith(adapter: AxiosAdapter) {
  return createApiClient({ baseURL: BASE, adapter })
}

async function caught(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError)
    return error as ApiError
  }
  throw new Error('expected the request to fail')
}

describe('resolveBaseUrl', () => {
  it('uses VITE_API_BASE_URL without a trailing slash', () => {
    expect(resolveBaseUrl({ VITE_API_BASE_URL: 'https://api.app.com/api/v1/', DEV: false })).toBe(
      'https://api.app.com/api/v1',
    )
  })

  it('falls back to the local backend in development', () => {
    expect(resolveBaseUrl({ DEV: true })).toBe(BASE)
  })

  it('refuses to guess in production', () => {
    expect(() => resolveBaseUrl({ DEV: false })).toThrow(/VITE_API_BASE_URL/)
  })
})

describe('createApiClient', () => {
  it('sends cookies, JSON and a timeout to the base URL', async () => {
    const adapter = vi.fn(respond(200, { ok: true }))
    await clientWith(adapter).get('/projects')
    const config = adapter.mock.calls[0][0]
    expect(config.baseURL).toBe(BASE)
    expect(config.url).toBe('/projects')
    // Access/refresh tokens are HTTPOnly cookies (research.md section 8).
    expect(config.withCredentials).toBe(true)
    expect(config.timeout).toBe(DEFAULT_TIMEOUT_MS)
    expect(config.headers.Accept).toBe('application/json')
  })

  it('returns the response data on success', async () => {
    const { data } = await clientWith(respond(200, { name: 'API' })).get('/')
    expect(data).toEqual({ name: 'API' })
  })

  it('each call builds an independent client', () => {
    expect(createApiClient({ baseURL: BASE })).not.toBe(createApiClient({ baseURL: BASE }))
  })
})

describe('error conversion', () => {
  it('reads the shared backend error body (T016)', async () => {
    const body = {
      error: 'not_found',
      message: '요청한 프로젝트를 찾을 수 없습니다.',
      details: { project_id: 'p1' },
      suggestion: '프로젝트 목록에서 다시 선택하세요.',
    }
    const error = await caught(clientWith(respond(404, body)).get('/projects/p1'))
    expect(error.status).toBe(404)
    expect(error.code).toBe('not_found')
    expect(error.message).toBe('요청한 프로젝트를 찾을 수 없습니다.')
    expect(error.details).toEqual({ project_id: 'p1' })
    expect(error.suggestion).toBe('프로젝트 목록에서 다시 선택하세요.')
  })

  it('keeps validation field messages', async () => {
    const body = {
      error: 'validation_error',
      message: '입력값이 올바르지 않습니다.',
      details: { fields: [{ field: 'email', message: '필수 입력 항목입니다.' }] },
    }
    const error = await caught(clientWith(respond(400, body)).post('/auth/register', {}))
    expect(error.fieldErrors).toEqual({ email: '필수 입력 항목입니다.' })
  })

  it('has no field errors when the body lists none', async () => {
    const noDetails = await caught(
      clientWith(respond(403, { error: 'forbidden', message: 'x' })).get('/'),
    )
    const otherDetails = await caught(
      clientWith(respond(409, { error: 'conflict', message: 'x', details: { id: 1 } })).get('/'),
    )
    expect(noDetails.fieldErrors).toEqual({})
    expect(otherDetails.fieldErrors).toEqual({})
    expect(noDetails.retryAfterSeconds).toBeUndefined()
  })

  it('reads Retry-After on 429', async () => {
    const body = {
      error: 'rate_limit_exceeded',
      message: '요청이 너무 많습니다. 8분 후 다시 시도하세요.',
    }
    const error = await caught(
      clientWith(respond(429, body, { 'retry-after': '480' })).post('/auth/login', {}),
    )
    expect(error.retryAfterSeconds).toBe(480)
  })

  it('uses a Korean fallback when the body is not our format', async () => {
    const error = await caught(clientWith(respond(502, '<html>Bad Gateway</html>')).get('/'))
    expect(error.status).toBe(502)
    expect(error.code).toBe('internal_error')
    expect(error.message).toBe(CLIENT_ERROR_MESSAGES.internal_error)
  })

  it('unknown 4xx without a body becomes bad_request', async () => {
    const error = await caught(clientWith(respond(418, '')).get('/'))
    expect(error.code).toBe('bad_request')
    expect(error.message).toBe(CLIENT_ERROR_MESSAGES.bad_request)
  })

  it('network failure has no status and a Korean message', async () => {
    const adapter: AxiosAdapter = (config) =>
      Promise.reject(new AxiosError('Network Error', AxiosError.ERR_NETWORK, config))
    const error = await caught(clientWith(adapter).get('/'))
    expect(error.status).toBeUndefined()
    expect(error.code).toBe('network_error')
    expect(error.message).toBe(CLIENT_ERROR_MESSAGES.network_error)
  })

  it('timeout has its own message', async () => {
    const adapter: AxiosAdapter = (config) =>
      Promise.reject(new AxiosError('timeout', AxiosError.ECONNABORTED, config))
    const error = await caught(clientWith(adapter).get('/'))
    expect(error.code).toBe('timeout')
    expect(error.message).toBe(CLIENT_ERROR_MESSAGES.timeout)
  })

  it('cancelled requests are passed through untouched', async () => {
    // TanStack Query cancels requests itself and must see the original error.
    const controller = new AbortController()
    controller.abort()
    const promise = clientWith(respond(200, {})).get('/', { signal: controller.signal })
    await expect(promise).rejects.not.toBeInstanceOf(ApiError)
    await expect(promise).rejects.toMatchObject({ code: 'ERR_CANCELED' })
  })

  it('works with the shared retry rules (T019)', async () => {
    const notFound = await caught(clientWith(respond(404, {})).get('/'))
    const serverError = await caught(clientWith(respond(503, {})).get('/'))
    const offline = await caught(
      clientWith((config) =>
        Promise.reject(new AxiosError('x', AxiosError.ERR_NETWORK, config)),
      ).get('/'),
    )
    expect(getHttpStatus(notFound)).toBe(404)
    expect(shouldRetryQuery(0, notFound)).toBe(false)
    expect(shouldRetryQuery(0, serverError)).toBe(true)
    expect(shouldRetryQuery(0, offline)).toBe(true)
  })

  it('is an Error with a readable name', async () => {
    const error = await caught(clientWith(respond(500, {})).get('/'))
    expect(error).toBeInstanceOf(Error)
    expect(error.name).toBe('ApiError')
  })
})
