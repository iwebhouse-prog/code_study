import { Link, NavLink, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { useLogout } from '../../hooks/useAuth'
import { paths } from '../../lib/paths'
import { useAuthStore } from '../../stores/auth-store'

const menuLink = ({ isActive }: { isActive: boolean }) =>
  cn(
    'rounded-md px-3 py-2 text-sm font-medium',
    isActive ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:text-foreground',
  )

// Top bar on every signed-in page (requirements-addendum navigation rules).
export default function TopNav() {
  const email = useAuthStore((state) => state.user?.email)
  return (
    <header className="border-b bg-background">
      <nav aria-label="주 메뉴" className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-4">
        <Link to={paths.dashboard} className="mr-4 text-lg font-bold">
          CodeLearn
        </Link>
        <NavLink to={paths.dashboard} end className={menuLink}>
          대시보드
        </NavLink>
        {/* No overall progress page exists yet; shown so the menu matches the spec. */}
        <span
          aria-disabled="true"
          title="준비 중입니다"
          className="cursor-not-allowed px-3 py-2 text-sm font-medium text-muted-foreground/60"
        >
          학습 진행률
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="ml-auto">
              {email}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {/* Rendered only while the menu is open, so pages that never open it
                need no QueryClientProvider for useLogout. */}
            <LogoutItem />
          </DropdownMenuContent>
        </DropdownMenu>
      </nav>
    </header>
  )
}

function LogoutItem() {
  const logout = useLogout()
  const navigate = useNavigate()
  return (
    <DropdownMenuItem
      onSelect={() => {
        // Leave first: once the session is cleared, ProtectedRoute would send
        // the user to /login remembering this page, and the next sign-in should
        // start at the dashboard instead.
        navigate(paths.login, { replace: true })
        void logout()
      }}
    >
      로그아웃
    </DropdownMenuItem>
  )
}
