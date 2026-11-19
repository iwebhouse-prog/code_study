import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import AuthStorePanel from '../../src/pages/dev/AuthStorePanel'
import DevTest from '../../src/pages/dev/DevTest'
import { TEST_USER } from '../../src/pages/dev/testUser'
import { useAuthStore } from '../../src/stores/auth-store'

const userCard = () => within(screen.getByRole('region', { name: '사용자 정보' }))
const flagCard = () => within(screen.getByRole('region', { name: '인증 여부' }))
const button = (name: string) => screen.getByRole('button', { name })

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
})

describe('AuthStorePanel', () => {
  it('shows the initial store state in both components', () => {
    render(<AuthStorePanel />)
    expect(userCard().getByText('user: null')).toBeInTheDocument()
    expect(flagCard().getByText('isAuthenticated: false')).toBeInTheDocument()
    expect(flagCard().getByText('status: unknown')).toBeInTheDocument()
  })

  it('"사용자 설정" updates both components at once', async () => {
    render(<AuthStorePanel />)
    await userEvent.click(button('사용자 설정'))
    expect(userCard().getByText(new RegExp(TEST_USER.email))).toBeInTheDocument()
    expect(flagCard().getByText('isAuthenticated: true')).toBeInTheDocument()
    expect(flagCard().getByText('status: authenticated')).toBeInTheDocument()
    expect(useAuthStore.getState().user).toEqual(TEST_USER)
  })

  it('"인증 초기화" clears both components at once', async () => {
    render(<AuthStorePanel />)
    await userEvent.click(button('사용자 설정'))
    await userEvent.click(button('인증 초기화'))
    expect(userCard().getByText('user: null')).toBeInTheDocument()
    expect(flagCard().getByText('isAuthenticated: false')).toBeInTheDocument()
    expect(flagCard().getByText('status: anonymous')).toBeInTheDocument()
  })
})

describe('/dev-test page', () => {
  it('keeps the API test and adds the store test', () => {
    render(<DevTest />)
    expect(button('API 호출')).toBeInTheDocument()
    expect(button('사용자 설정')).toBeInTheDocument()
  })
})
