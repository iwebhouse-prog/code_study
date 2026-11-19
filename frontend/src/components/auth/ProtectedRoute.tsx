import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { paths } from '../../lib/paths'
import { useAuthStore } from '../../stores/auth-store'

// Guards the signed-in pages. While the session check is still running the
// answer is unknown, so wait instead of bouncing signed-in users to /login.
export default function ProtectedRoute({ children }: { children?: ReactNode }) {
  const status = useAuthStore((state) => state.status)
  const location = useLocation()

  if (status === 'unknown') {
    return (
      <p role="status" className="p-8 text-center text-muted-foreground">
        로그인 상태를 확인하는 중입니다…
      </p>
    )
  }
  if (status === 'anonymous') {
    // Login reads `from` to send the visitor back where they were heading.
    const from = location.pathname + location.search + location.hash
    return <Navigate to={paths.login} state={{ from }} replace />
  }
  return children ?? <Outlet />
}
