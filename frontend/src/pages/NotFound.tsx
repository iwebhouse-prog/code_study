import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card'
import { paths } from '../lib/paths'

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <Card className="w-full max-w-md text-center">
        <CardHeader>
          <h1 className="text-xl font-semibold">페이지를 찾을 수 없습니다</h1>
          <CardDescription>요청한 페이지를 찾을 수 없습니다.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link to={paths.dashboard}>내 프로젝트로 이동</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  )
}
