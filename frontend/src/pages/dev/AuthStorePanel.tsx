import { useAuthStore } from '../../stores/auth-store'
import { TEST_USER } from './testUser'

// Each card subscribes to the store by itself and gets no props, so both
// changing on one click proves the store, not a parent, keeps them in sync.
function UserCard() {
  const user = useAuthStore((state) => state.user)
  return (
    <section aria-label="사용자 정보">
      <h3>컴포넌트 A: user</h3>
      <p>user: {user ? JSON.stringify(user) : 'null'}</p>
    </section>
  )
}

function AuthFlagCard() {
  const status = useAuthStore((state) => state.status)
  return (
    <section aria-label="인증 여부">
      <h3>컴포넌트 B: isAuthenticated</h3>
      <p>isAuthenticated: {String(status === 'authenticated')}</p>
      <p>status: {status}</p>
    </section>
  )
}

export default function AuthStorePanel() {
  const setUser = useAuthStore((state) => state.setUser)
  const clearUser = useAuthStore((state) => state.clearUser)
  return (
    <section aria-label="Zustand 스토어 테스트">
      <h2>Zustand 인증 스토어 테스트</h2>
      <button type="button" onClick={() => setUser(TEST_USER)}>
        사용자 설정
      </button>
      <button type="button" onClick={clearUser}>
        인증 초기화
      </button>
      <UserCard />
      <AuthFlagCard />
    </section>
  )
}
