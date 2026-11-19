import { describe, expect, it, vi } from 'vitest'
import { ApiError, createApiClient } from '../../src/services/api-client'
import { installSessionRefresh } from '../../src/services/auth-refresh'
import { adapterFor, errorReply, type Handler, type RecordedRequest } from '../helpers/http'

function setup(handler: Handler, refreshImpl?: () => Promise<unknown>) {
  const calls: RecordedRequest[] = []
  const client = createApiClient({
    baseURL: 'http://localhost:8000/api/v1',
    adapter: adapterFor((req) => {
      calls.push(req)
      return handler(req)
    }),
  })
  const refresh = vi.fn(refreshImpl ?? (() => Promise.resolve({})))
  const onSessionEnded = vi.fn()
  const uninstall = installSessionRefresh(client, { refresh, onSessionEnded })
  return { client, calls, refresh, onSessionEnded, uninstall }
}

/** First call says token_expired; later calls succeed. */
function expireOnce(): Handler {
  let served = 0
  return () => {
    served += 1
    return served === 1 ? errorReply(401, 'token_expired') : { status: 200, data: { ok: true } }
  }
}

describe('installSessionRefresh', () => {
  it('refreshes once on token_expired and retries the original request once', async () => {
    const { client, calls, refresh, onSessionEnded } = setup(expireOnce())
    const response = await client.get('/projects')
    expect(response.data).toEqual({ ok: true })
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(calls.map((c) => c.url)).toEqual(['/projects', '/projects'])
    expect(onSessionEnded).not.toHaveBeenCalled()
  })

  it('retries a POST with its original body', async () => {
    const { client, calls } = setup(expireOnce())
    await client.post('/projects', { name: 'x' })
    expect(calls[1]).toEqual({ method: 'post', url: '/projects', body: { name: 'x' } })
  })

  it('shares ONE refresh between concurrent token_expired answers', async () => {
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const seen = new Set<string>()
    const { client, refresh, calls } = setup(
      (req) => {
        if (seen.has(req.url)) return { status: 200, data: req.url }
        seen.add(req.url)
        return errorReply(401, 'token_expired')
      },
      () => gate,
    )
    const all = Promise.all([client.get('/a'), client.get('/b'), client.get('/c')])
    await vi.waitFor(() => expect(refresh).toHaveBeenCalled())
    expect(calls).toHaveLength(3)
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(refresh).toHaveBeenCalledTimes(1)
    release()
    const results = await all
    expect(results.map((r) => r.data)).toEqual(['/a', '/b', '/c'])
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('starts a fresh refresh for a later expiry', async () => {
    let served = 0
    const { client, refresh } = setup(() => {
      served += 1
      return served % 2 === 1 ? errorReply(401, 'token_expired') : { status: 200 }
    })
    await client.get('/one')
    await client.get('/two')
    expect(refresh).toHaveBeenCalledTimes(2)
  })

  it('does not retry a second time when the retry is expired again', async () => {
    const { client, refresh, calls } = setup(() => errorReply(401, 'token_expired'))
    await expect(client.get('/projects')).rejects.toMatchObject({ code: 'token_expired' })
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(calls).toHaveLength(2)
  })

  it('ends the session when the refresh fails', async () => {
    const failure = new ApiError({ status: 401, code: 'session_expired', message: '만료' })
    const { client, onSessionEnded, calls } = setup(expireOnce(), () => Promise.reject(failure))
    await expect(client.get('/projects')).rejects.toBe(failure)
    expect(onSessionEnded).toHaveBeenCalled()
    expect(calls).toHaveLength(1)
  })

  it('ends the session on session_expired without refreshing', async () => {
    const { client, refresh, onSessionEnded } = setup(() => errorReply(401, 'session_expired'))
    await expect(client.get('/projects')).rejects.toMatchObject({ code: 'session_expired' })
    expect(refresh).not.toHaveBeenCalled()
    expect(onSessionEnded).toHaveBeenCalledTimes(1)
  })

  it('does not refresh for the refresh request itself (no deadlock)', async () => {
    const { client, refresh } = setup(() => errorReply(401, 'token_expired'))
    await expect(client.post('/auth/refresh')).rejects.toMatchObject({ code: 'token_expired' })
    expect(refresh).not.toHaveBeenCalled()
  })

  it('leaves other errors alone', async () => {
    const { client, refresh, onSessionEnded } = setup(() =>
      errorReply(401, 'invalid_credentials', '틀림'),
    )
    await expect(client.post('/auth/login', {})).rejects.toMatchObject({
      code: 'invalid_credentials',
    })
    expect(refresh).not.toHaveBeenCalled()
    expect(onSessionEnded).not.toHaveBeenCalled()
  })

  it('passes non-API errors (cancellation) through untouched', async () => {
    const { client } = setup(() => ({ status: 200 }))
    const controller = new AbortController()
    controller.abort()
    await expect(client.get('/x', { signal: controller.signal })).rejects.toMatchObject({
      code: 'ERR_CANCELED',
    })
  })

  it('stops acting once uninstalled', async () => {
    const { client, refresh, uninstall } = setup(expireOnce())
    uninstall()
    await expect(client.get('/projects')).rejects.toMatchObject({ code: 'token_expired' })
    expect(refresh).not.toHaveBeenCalled()
  })
})
