import { describe, expect, it } from 'vitest'
import { createApiClient } from '../../src/services/api-client'
import { createAuthService, toAuthUser } from '../../src/services/auth-service'
import {
  APP_USER,
  RAW_USER,
  adapterFor,
  errorReply,
  type Handler,
  type RecordedRequest,
} from '../helpers/http'

function serviceWith(reply: Handler) {
  const calls: RecordedRequest[] = []
  const client = createApiClient({
    baseURL: 'http://localhost:8000/api/v1',
    adapter: adapterFor((req) => {
      calls.push(req)
      return reply(req)
    }),
  })
  return { service: createAuthService(client), calls }
}

describe('toAuthUser', () => {
  it('maps the snake_case body to AuthUser and drops the rest', () => {
    expect(toAuthUser(RAW_USER)).toEqual(APP_USER)
  })
})

describe('auth service', () => {
  it('register posts email and password and returns the signed-in user', async () => {
    const { service, calls } = serviceWith(() => ({ status: 201, data: RAW_USER }))
    const user = await service.register({ email: 'a@b.com', password: 'abcd1234' })
    expect(user).toEqual(APP_USER)
    expect(calls).toEqual([
      { method: 'post', url: '/auth/register', body: { email: 'a@b.com', password: 'abcd1234' } },
    ])
  })

  it('login posts email and password and returns the user', async () => {
    const { service, calls } = serviceWith(() => ({ status: 200, data: RAW_USER }))
    const user = await service.login({ email: 'a@b.com', password: 'abcd1234' })
    expect(user).toEqual(APP_USER)
    expect(calls[0]).toMatchObject({ method: 'post', url: '/auth/login' })
  })

  it('me reads the current user', async () => {
    const { service, calls } = serviceWith(() => ({ status: 200, data: RAW_USER }))
    expect(await service.me()).toEqual(APP_USER)
    expect(calls[0]).toMatchObject({ method: 'get', url: '/auth/me' })
  })

  it('refresh posts to /auth/refresh and returns the user', async () => {
    const { service, calls } = serviceWith(() => ({ status: 200, data: RAW_USER }))
    expect(await service.refresh()).toEqual(APP_USER)
    expect(calls[0]).toMatchObject({ method: 'post', url: '/auth/refresh' })
  })

  it('logout posts to /auth/logout and resolves with nothing', async () => {
    const { service, calls } = serviceWith(() => ({ status: 204 }))
    expect(await service.logout()).toBeUndefined()
    expect(calls[0]).toMatchObject({ method: 'post', url: '/auth/logout' })
  })

  it('lets ApiError through so forms can show field errors', async () => {
    const { service } = serviceWith(() =>
      errorReply(409, 'email_taken', '이미 가입된 이메일입니다.'),
    )
    await expect(
      service.register({ email: 'a@b.com', password: 'abcd1234' }),
    ).rejects.toMatchObject({ status: 409, code: 'email_taken' })
  })
})
