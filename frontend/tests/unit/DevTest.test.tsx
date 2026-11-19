import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { createQueryClient } from '../../src/lib/queryClient'
import DevTest from '../../src/pages/dev/DevTest'
import { routes } from '../../src/routes'
import { createApiClient } from '../../src/services/api-client'

const BASE = 'http://localhost:8000/api/v1'

function respond(status: number, data: unknown): AxiosAdapter {
  return (config: InternalAxiosRequestConfig) => {
    const response: AxiosResponse = {
      data,
      status,
      statusText: '',
      headers: new AxiosHeaders(),
      config,
    }
    return status < 400
      ? Promise.resolve(response)
      : Promise.reject(new AxiosError('fail', 'ERR_BAD_RESPONSE', config, {}, response))
  }
}

function renderPage(adapter: AxiosAdapter) {
  render(<DevTest client={createApiClient({ baseURL: BASE, adapter })} />)
}

const callButton = () => screen.getByRole('button', { name: 'API 호출' })

describe('DevTest page', () => {
  it('shows the button and an empty result area first', () => {
    renderPage(respond(200, {}))
    expect(callButton()).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('아직 호출하지 않았습니다')
  })

  it('calls GET /health on the API base URL', async () => {
    const adapter = vi.fn(respond(200, { status: 'ok', database: 'ok' }))
    renderPage(adapter)
    await userEvent.click(callButton())
    const config = adapter.mock.calls[0][0]
    expect(config.method).toBe('get')
    expect(`${config.baseURL}${config.url}`).toBe(`${BASE}/health`)
  })

  it('shows status code and JSON body on success', async () => {
    renderPage(respond(200, { status: 'ok', database: 'ok' }))
    await userEvent.click(callButton())
    expect(await screen.findByText(/HTTP 200/)).toBeInTheDocument()
    expect(screen.getByText(/"database": "ok"/)).toBeInTheDocument()
    expect(screen.getByText(/GET http:\/\/localhost:8000\/api\/v1\/health/)).toBeInTheDocument()
  })

  it('shows the API error when the database is down', async () => {
    renderPage(respond(503, { status: 'unavailable', database: 'unavailable' }))
    await userEvent.click(callButton())
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('HTTP 503')
  })

  it('shows the Korean message when the server is unreachable', async () => {
    renderPage((config) => Promise.reject(new AxiosError('x', AxiosError.ERR_NETWORK, config)))
    await userEvent.click(callButton())
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('network_error')
    expect(alert).toHaveTextContent('서버에 연결할 수 없습니다')
  })

  it('shows unexpected non-API errors too', async () => {
    renderPage(() => Promise.reject(new TypeError('adapter broke')))
    await userEvent.click(callButton())
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('응답 없음')
    expect(alert).toHaveTextContent('unknown')
    expect(alert).toHaveTextContent('adapter broke')
  })

  it('disables the button while the call is running', async () => {
    let finish: () => void = () => {}
    renderPage(
      (config) =>
        new Promise((resolve) => {
          finish = () => resolve(respond(200, { status: 'ok' })(config))
        }),
    )
    await userEvent.click(callButton())
    expect(screen.getByRole('button', { name: '호출 중...' })).toBeDisabled()
    finish()
    expect(await screen.findByText(/HTTP 200/)).toBeInTheDocument()
    expect(callButton()).toBeEnabled()
  })
})

describe('dev route', () => {
  it('/dev-test opens the page in development', async () => {
    const router = createMemoryRouter(routes, { initialEntries: ['/dev-test'] })
    render(
      <QueryClientProvider client={createQueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )
    expect(
      await screen.findByRole('heading', { level: 1, name: 'API 연결 테스트' }),
    ).toBeInTheDocument()
  })
})
