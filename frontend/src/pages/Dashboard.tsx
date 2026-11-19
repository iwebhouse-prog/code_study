import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import CreateProjectModal from '@/components/project/CreateProjectModal'
import ProjectCard from '@/components/project/ProjectCard'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { paths } from '@/lib/paths'
import { PROJECTS_KEY } from '@/lib/query-keys'
import { projectService, type NewProject } from '@/services/project-service'
import { useToastStore } from '@/stores/toast-store'

export default function Dashboard() {
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const showToast = useToastStore((state) => state.show)
  const projects = useQuery({ queryKey: PROJECTS_KEY, queryFn: projectService.list })

  async function createProject(input: NewProject) {
    const project = await projectService.create(input)
    void queryClient.invalidateQueries({ queryKey: PROJECTS_KEY })
    showToast('프로젝트가 생성되었습니다.')
    navigate(paths.project(project.id))
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">내 프로젝트</h1>
        <Button onClick={() => setCreating(true)}>새 프로젝트</Button>
      </div>

      {projects.isPending && (
        <p role="status" className="text-muted-foreground">
          프로젝트를 불러오는 중입니다…
        </p>
      )}
      {projects.isError && (
        <div className="space-y-3">
          <Alert variant="destructive">{projects.error.message}</Alert>
          <Button variant="outline" onClick={() => void projects.refetch()}>
            다시 시도
          </Button>
        </div>
      )}
      {projects.isSuccess && projects.data.length === 0 && (
        <section className="space-y-3 py-12 text-center">
          <p aria-hidden="true" className="text-5xl">
            📁
          </p>
          <h2 className="text-xl font-semibold">아직 프로젝트가 없습니다</h2>
          <p className="text-muted-foreground">
            프로젝트를 만들어 AI 코드 학습을 시작하세요. 프로젝트는 관련된 학습 태스크들을 모아둔
            폴더입니다.
          </p>
          <Button onClick={() => setCreating(true)}>첫 프로젝트 만들기</Button>
          <p className="text-sm text-muted-foreground">예: '나의 Todo 앱', '계산기 프로그램'</p>
        </section>
      )}
      {projects.isSuccess && projects.data.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.data.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}

      <CreateProjectModal open={creating} onOpenChange={setCreating} onSubmit={createProject} />
    </main>
  )
}
