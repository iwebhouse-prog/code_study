import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { apiClient } from '../../src/services/api-client'

export interface Reply {
  status: number
  data?: unknown
}

export interface RecordedRequest {
  method: string
  url: string
  body: unknown
}

export type Handler = (request: RecordedRequest) => Reply | Promise<Reply>

export const RAW_USER = {
  id: '12345678-1234-5678-1234-567812345678',
  email: 'student@example.com',
  skill_level: 'Complete Beginner',
  created_at: '2026-11-09T01:00:00+00:00',
  last_login_at: null,
}

export const APP_USER = {
  id: RAW_USER.id,
  email: RAW_USER.email,
  skillLevel: 'Complete Beginner',
}

export function errorReply(
  status: number,
  error: string,
  message = '오류',
  details?: Record<string, unknown>,
): Reply {
  return { status, data: { error, message, details } }
}

export function adapterFor(handler: Handler): AxiosAdapter {
  return async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
    const reply = await handler({
      method: (config.method ?? 'get').toLowerCase(),
      url: config.url ?? '',
      body,
    })
    const response: AxiosResponse = {
      data: reply.data,
      status: reply.status,
      statusText: String(reply.status),
      headers: new AxiosHeaders(),
      config,
    }
    if (reply.status < 400) return response
    throw new AxiosError(`HTTP ${reply.status}`, 'ERR_BAD_RESPONSE', config, {}, response)
  }
}

const originalAdapter = apiClient.defaults.adapter

/** Routes every call of the shared apiClient to `handler`; returns the call log. */
export function mockApiClient(handler: Handler): RecordedRequest[] {
  const calls: RecordedRequest[] = []
  apiClient.defaults.adapter = adapterFor((request) => {
    calls.push(request)
    return handler(request)
  })
  return calls
}

export function restoreApiClient(): void {
  apiClient.defaults.adapter = originalAdapter
}
