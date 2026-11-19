import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { DocumentViewer } from '@/components/document/DocumentViewer'
import { Alert } from '@/components/ui/alert'
import { Tabs } from '@/components/ui/tabs'
import { paths } from '@/lib/paths'
import { taskKey } from '@/lib/query-keys'
import { taskService, type Task } from '@/services/task-service'

const TABS = [
  { id: 'document', label: '학습 문서' },
  { id: 'practice', label: '연습 문제' },
  { id: 'qa', label: '질문하기' },
] as const

type TabId = (typeof TABS)[number]['id']

// Practice and Q&A tabs arrive in later phases.
const PLACEHOLDERS = {
  practice: '연습 문제는 곧 제공됩니다.',
  qa: '질문하기는 곧 제공됩니다.',
} as const

function TaskView({ task }: { task: Task }) {
  const [tab, setTab] = useState<TabId>('document')
  return (
    <>
      <Link to={paths.project(task.projectId)} className="text-sm text-primary hover:underline">
        프로젝트로 돌아가기
      </Link>
      <h1 className="text-2xl font-bold">
        Task {task.taskNumber}. {task.title}
      </h1>
      {task.description && <p className="text-muted-foreground">{task.description}</p>}
      <Tabs label="태스크 학습 도구" tabs={TABS} value={tab} onValueChange={setTab}>
        {tab === 'document' ? (
          <DocumentViewer taskId={task.id} />
        ) : (
          <p className="text-muted-foreground">{PLACEHOLDERS[tab]}</p>
        )}
      </Tabs>
    </>
  )
}

export default function TaskDetail() {
  const { taskId = '' } = useParams()
  const query = useQuery({
    queryKey: taskKey(taskId),
    queryFn: () => taskService.get(taskId),
  })

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      {query.isPending && (
        <p role="status" className="text-muted-foreground">
          태스크를 불러오는 중입니다…
        </p>
      )}
      {query.isError && (
        <>
          <h1 className="text-2xl font-bold">태스크를 열 수 없습니다</h1>
          <Alert variant="destructive">{query.error.message}</Alert>
          <Link to={paths.dashboard} className="text-sm text-primary hover:underline">
            내 프로젝트로 돌아가기
          </Link>
        </>
      )}
      {query.isSuccess && <TaskView task={query.data} />}
    </main>
  )
}
