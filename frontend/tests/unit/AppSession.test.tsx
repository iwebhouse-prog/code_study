import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import App from '../../src/App'
import { useAuthStore } from '../../src/stores/auth-store'
import { RAW_USER, errorReply, mockApiClient, restoreApiClient } from '../helpers/http'

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
})

afterEach(() => {
  restoreApiClient()
})

describe('App session check on start', () => {
  it('shows a signed-in page after GET /auth/me confirms the cookie', async () => {
    mockApiClient(() => ({ status: 200, data: RAW_USER }))
    window.history.pushState({}, '', '/trash')
    render(<App />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '휴지통' })).toBeInTheDocument()
  })

  it('sends visitors without a session to the login page', async () => {
    mockApiClient(() => errorReply(401, 'unauthorized'))
    window.history.pushState({}, '', '/trash')
    render(<App />)
    expect(await screen.findByRole('heading', { name: '로그인' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
  })
})
