import { Link, useNavigate } from 'react-router-dom'
import RegisterForm from '@/components/auth/RegisterForm'
import { Card, CardContent, CardDescription, CardFooter, CardHeader } from '@/components/ui/card'
import { useAuth } from '../hooks/useAuth'
import { paths } from '../lib/paths'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <h1 className="text-xl font-semibold">회원가입</h1>
          <CardDescription>비밀번호는 8자 이상, 영문자와 숫자를 포함해야 합니다.</CardDescription>
        </CardHeader>
        <CardContent>
          <RegisterForm
            onSubmit={async (credentials) => {
              // The server signs the new user in, so go straight to the dashboard.
              await register(credentials)
              navigate(paths.dashboard, { replace: true })
            }}
          />
        </CardContent>
        <CardFooter className="text-sm">
          <span>
            이미 계정이 있나요?{' '}
            <Link to={paths.login} className="font-medium underline">
              로그인
            </Link>
          </span>
        </CardFooter>
      </Card>
    </main>
  )
}
