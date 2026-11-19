import { useQueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

// Swap the real pages for one that reads the query client from context.
vi.mock('../../src/routes', () => {
  function ClientProbe() {
    const staleTime = useQueryClient().getDefaultOptions().queries?.staleTime
    return <p>staleTime={String(staleTime)}</p>
  }
  return { routes: [{ path: '*', element: <ClientProbe /> }] }
})

const { default: App } = await import('../../src/App')

describe('App providers', () => {
  it('every page can use the shared query client', () => {
    render(<App />)
    expect(screen.getByText('staleTime=30000')).toBeInTheDocument()
  })
})
