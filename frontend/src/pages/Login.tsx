import { Link, useLocation, useNavigate } from 'react-router-dom'
import LoginForm from '@/components/auth/LoginForm'
import { Card, CardContent, CardDescription, CardFooter, CardHeader } from '@/components/ui/card'
import { useAuth } from '../hooks/useAuth'
import { paths } from '../lib/paths'

// Only in-app paths count: "//host" and "http://..." would send the user to another site.
function safeTarget(from: unknown): string {
  return typeof from === 'string' && from.startsWith('/') && !from.startsWith('//')
    ? from
    : paths.dashboard
}

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const target = safeTarget((location.state as { from?: unknown } | null)?.from)

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <h1 className="text-xl font-semibold">로그인</h1>
          <CardDescription>이메일과 비밀번호를 입력하세요.</CardDescription>
        </CardHeader>
        <CardContent>
          <LoginForm
            onSubmit={async (credentials) => {
              await login(credentials)
              navigate(target, { replace: true })
            }}
          />
        </CardContent>
        <CardFooter className="text-sm">
          <span>
            계정이 없나요?{' '}
            <Link to={paths.register} className="font-medium underline">
              회원가입
            </Link>
          </span>
        </CardFooter>
      </Card>
    </main>
  )
}
