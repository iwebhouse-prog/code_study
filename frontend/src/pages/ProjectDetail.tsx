import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import CreateProjectModal from '@/components/project/CreateProjectModal'
import DeleteProjectDialog from '@/components/project/DeleteProjectDialog'
import CreateTaskModal from '@/components/task/CreateTaskModal'
import TaskCard from '@/components/task/TaskCard'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { formatKoreanDate } from '@/lib/format'
import { paths } from '@/lib/paths'
import { PROJECTS_KEY, projectKey, projectTasksKey } from '@/lib/query-keys'
import {
  projectService,
  type NewProject,
  type Project,
  type ProjectChanges,
} from '@/services/project-service'
import { taskService } from '@/services/task-service'
import { useToastStore } from '@/stores/toast-store'

function BackLink() {
  return (
    <Link to={paths.dashboard} className="text-sm text-primary hover:underline">
      내 프로젝트로 돌아가기
    </Link>
  )
}

function TaskSection({ projectId }: { projectId: string }) {
  const [creating, setCreating] = useState(false)
  const tasks = useQuery({
    queryKey: projectTasksKey(projectId),
    queryFn: () => taskService.list(projectId),
  })

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">태스크</h2>
        {tasks.isSuccess && tasks.data.length > 0 && (
          <Button onClick={() => setCreating(true)}>태스크 추가</Button>
        )}
      </div>
      {tasks.isPending && (
        <p role="status" className="text-muted-foreground">
          태스크를 불러오는 중입니다…
        </p>
      )}
      {tasks.isError && (
        <div className="space-y-3">
          <Alert variant="destructive">{tasks.error.message}</Alert>
          <Button variant="outline" onClick={() => void tasks.refetch()}>
            다시 시도
          </Button>
        </div>
      )}
      {tasks.isSuccess && tasks.data.length === 0 && (
        <div className="space-y-3 rounded-xl border border-dashed p-6 text-center">
          <p aria-hidden="true" className="text-4xl">
            📝
          </p>
          <h3 className="text-lg font-semibold">아직 태스크가 없습니다</h3>
          <p className="text-muted-foreground">
            코드를 업로드하고 학습 자료를 생성하려면 태스크를 추가하세요.
          </p>
          <Button onClick={() => setCreating(true)}>첫 태스크 추가</Button>
          <p className="text-sm text-muted-foreground">
            💡 팁: 작은 코드 단위로 나누어 학습하면 이해가 쉬워집니다.
          </p>
        </div>
      )}
      {tasks.isSuccess && tasks.data.length > 0 && (
        <ul aria-label="태스크 목록" className="space-y-3">
          {[...tasks.data]
            .sort((a, b) => a.taskNumber - b.taskNumber)
            .map((task) => (
              <li key={task.id}>
                <TaskCard task={task} />
              </li>
            ))}
        </ul>
      )}
      <CreateTaskModal projectId={projectId} open={creating} onOpenChange={setCreating} />
    </section>
  )
}

function ProjectView({ project }: { project: Project }) {
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const showToast = useToastStore((state) => state.show)

  async function saveChanges({ title, description }: NewProject) {
    // PATCH carries only what changed; a blank description clears it (null).
    const changes: ProjectChanges = {}
    if (title !== project.title) changes.title = title
    if ((description ?? null) !== project.description) changes.description = description ?? null
    if (Object.keys(changes).length === 0) return

    const updated = await projectService.update(project.id, changes)
    queryClient.setQueryData(projectKey(project.id), updated)
    void queryClient.invalidateQueries({ queryKey: PROJECTS_KEY, exact: true })
    showToast('프로젝트가 수정되었습니다.')
  }

  async function deleteProject() {
    await projectService.remove(project.id)
    void queryClient.invalidateQueries({ queryKey: PROJECTS_KEY, exact: true })
    showToast('프로젝트가 휴지통으로 이동되었습니다.')
    navigate(paths.dashboard)
    queryClient.removeQueries({ queryKey: projectKey(project.id) })
  }

  return (
    <>
      <BackLink />
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-bold">{project.title}</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditing(true)}>
            수정
          </Button>
          <Button variant="destructive" onClick={() => setDeleting(true)}>
            삭제
          </Button>
        </div>
      </div>
      <p className="text-muted-foreground">{project.description ?? '설명이 없습니다.'}</p>
      <section className="space-y-1 text-sm text-muted-foreground">
        <h2 className="text-lg font-semibold text-foreground">프로젝트 상세</h2>
        <p>
          완료 {project.completedTaskCount}/{project.taskCount} 태스크
        </p>
        <p>만든 날짜: {formatKoreanDate(project.createdAt)}</p>
        <p>마지막 활동: {formatKoreanDate(project.lastActivityAt)}</p>
      </section>
      <TaskSection projectId={project.id} />

      <CreateProjectModal
        open={editing}
        onOpenChange={setEditing}
        onSubmit={saveChanges}
        project={project}
      />
      <DeleteProjectDialog
        open={deleting}
        onOpenChange={setDeleting}
        projectTitle={project.title}
        onConfirm={deleteProject}
      />
    </>
  )
}

export default function ProjectDetail() {
  const { projectId = '' } = useParams()
  const query = useQuery({
    queryKey: projectKey(projectId),
    queryFn: () => projectService.get(projectId),
  })

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      {query.isPending && (
        <p role="status" className="text-muted-foreground">
          프로젝트를 불러오는 중입니다…
        </p>
      )}
      {query.isError && (
        <>
          <h1 className="text-2xl font-bold">프로젝트를 열 수 없습니다</h1>
          <Alert variant="destructive">{query.error.message}</Alert>
          <BackLink />
        </>
      )}
      {query.isSuccess && <ProjectView project={query.data} />}
    </main>
  )
}
