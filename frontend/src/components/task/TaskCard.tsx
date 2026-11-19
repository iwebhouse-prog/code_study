import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { formatKoreanDate } from '@/lib/format'
import { languageLabel } from '@/lib/languages'
import { paths } from '@/lib/paths'
import type { Task } from '@/services/task-service'

export default function TaskCard({ task }: { task: Task }) {
  const language = task.code?.detectedLanguage
  return (
    <Card>
      <CardHeader>
        <p className="text-sm font-medium text-muted-foreground">Task {task.taskNumber}</p>
        <h3 className="font-semibold leading-none tracking-tight">
          <Link to={paths.task(task.id)} className="hover:underline">
            {task.title}
          </Link>
        </h3>
      </CardHeader>
      <CardContent className="space-y-1 text-sm text-muted-foreground">
        <p>만든 날짜: {formatKoreanDate(task.createdAt)}</p>
        <p>{language ? languageLabel(language) : '분석 중'}</p>
      </CardContent>
    </Card>
  )
}
