import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { formatKoreanDate } from '@/lib/format'
import { paths } from '@/lib/paths'
import type { Project } from '@/services/project-service'

export default function ProjectCard({ project }: { project: Project }) {
  return (
    <Card>
      <CardHeader>
        <h2 className="font-semibold leading-none tracking-tight">
          <Link to={paths.project(project.id)} className="hover:underline">
            {project.title}
          </Link>
        </h2>
        {project.description && (
          <p className="text-sm text-muted-foreground">{project.description}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-1 text-sm text-muted-foreground">
        <p>
          완료 {project.completedTaskCount}/{project.taskCount} 태스크
        </p>
        <p>마지막 활동: {formatKoreanDate(project.lastActivityAt)}</p>
      </CardContent>
    </Card>
  )
}
