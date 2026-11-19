import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { createQueryClient } from '../../src/lib/queryClient'
import QueryTest from '../../src/pages/dev/QueryTest'
import { fetchDummyProjects } from '../../src/pages/dev/dummyApi'
import { routes } from '../../src/routes'

function renderPage() {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <QueryTest delayMs={0} retryDelayMs={0} />
    </QueryClientProvider>,
  )
}

describe('fetchDummyProjects', () => {
  it('resolves with dummy projects on success', async () => {
    const projects = await fetchDummyProjects('success', 0)
    expect(projects.map((p) => p.title)).toEqual([
      'Python 기초 다지기',
      'React 할 일 앱',
      'FastAPI 로그인 만들기',
    ])
  })

  it.each([
    ['notfound', 404],
    ['server-error', 503],
  ] as const)('rejects %s with HTTP status %i', async (mode, status) => {
    await expect(fetchDummyProjects(mode, 0)).rejects.toMatchObject({
      response: { status },
    })
  })
})

describe('QueryTest page', () => {
  it('shows loading, then the projects', async () => {
    renderPage()
    expect(screen.getByRole('status')).toHaveTextContent('불러오는 중')
    expect(await screen.findByText('Python 기초 다지기')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('성공')
  })

  it('404 fails after a single attempt', async () => {
    renderPage()
    await screen.findByText('Python 기초 다지기')
    await userEvent.click(screen.getByRole('button', { name: '404 오류' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('404')
    expect(alert).toHaveTextContent('시도 횟수: 1')
  })

  it('503 is retried twice before failing', async () => {
    renderPage()
    await screen.findByText('Python 기초 다지기')
    await userEvent.click(screen.getByRole('button', { name: '503 오류' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('503')
    expect(alert).toHaveTextContent('시도 횟수: 3')
  })

  it('can switch back to success after an error', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: '404 오류' }))
    await screen.findByRole('alert')
    await userEvent.click(screen.getByRole('button', { name: '성공' }))
    expect(await screen.findByText('React 할 일 앱')).toBeInTheDocument()
  })

  it('refetch button loads again', async () => {
    renderPage()
    await screen.findByText('Python 기초 다지기')
    await userEvent.click(screen.getByRole('button', { name: '다시 불러오기' }))
    expect(await screen.findByText('Python 기초 다지기')).toBeInTheDocument()
  })
})

describe('dev route', () => {
  it('/dev/query-test opens the page in development', async () => {
    const router = createMemoryRouter(routes, { initialEntries: ['/dev/query-test'] })
    render(
      <QueryClientProvider client={createQueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    )
    expect(
      await screen.findByRole('heading', { level: 1, name: 'TanStack Query 테스트' }),
    ).toBeInTheDocument()
  })
})
