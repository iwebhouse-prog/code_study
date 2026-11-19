import { useId, useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/services/api-client'
import type { NewProject, Project } from '@/services/project-service'

export const TITLE_MAX_LENGTH = 255

// The same dialog creates a project or, when given one, edits it.
const TEXTS = {
  create: {
    heading: '새 프로젝트',
    submit: '만들기',
    pending: '만드는 중…',
    failure: '프로젝트를 만들지 못했습니다. 잠시 후 다시 시도하세요.',
  },
  edit: {
    heading: '프로젝트 수정',
    submit: '저장',
    pending: '저장하는 중…',
    failure: '프로젝트를 저장하지 못했습니다. 잠시 후 다시 시도하세요.',
  },
}

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Saves the project; a rejection keeps the dialog open and is shown in it. */
  onSubmit: (project: NewProject) => Promise<void>
  /** Edit this project instead of creating a new one. */
  project?: Project
}

// Same rule as the backend (title 1-255 characters after trimming); this check
// only saves a round trip, the server's answer is final.
function checkTitle(title: string): string | undefined {
  if (title.length < 1) return '프로젝트 제목은 최소 1자 이상이어야 합니다.'
  if (title.length > TITLE_MAX_LENGTH) return '프로젝트 제목은 255자를 넘을 수 없습니다.'
  return undefined
}

function ProjectForm({
  onSubmit,
  onClose,
  project,
}: {
  onSubmit: Props['onSubmit']
  onClose: () => void
  project?: Project
}) {
  const texts = project ? TEXTS.edit : TEXTS.create
  const id = useId()
  const [titleError, setTitleError] = useState<string>()
  const [formError, setFormError] = useState<string>()
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const title = String(data.get('title')).trim()
    const description = String(data.get('description')).trim()

    const problem = checkTitle(title)
    setFormError(undefined)
    setTitleError(problem)
    if (problem) return

    setPending(true)
    try {
      await onSubmit(description ? { title, description } : { title })
      onClose()
    } catch (error) {
      if (error instanceof ApiError) {
        setTitleError(error.fieldErrors.title)
        setFormError(error.fieldErrors.title ? undefined : error.message)
      } else {
        setFormError(texts.failure)
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      {formError && <Alert variant="destructive">{formError}</Alert>}
      <div className="space-y-2">
        <Label htmlFor={`${id}-title`}>프로젝트 제목</Label>
        <Input
          id={`${id}-title`}
          name="title"
          defaultValue={project?.title}
          required
          aria-invalid={titleError ? true : undefined}
          aria-describedby={titleError ? `${id}-title-error` : undefined}
        />
        {titleError && (
          <p id={`${id}-title-error`} className="text-sm text-destructive">
            {titleError}
          </p>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${id}-description`}>설명 (선택)</Label>
        <Input
          id={`${id}-description`}
          name="description"
          defaultValue={project?.description ?? ''}
        />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          취소
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? texts.pending : texts.submit}
        </Button>
      </DialogFooter>
    </form>
  )
}

export default function CreateProjectModal({ open, onOpenChange, onSubmit, project }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{(project ? TEXTS.edit : TEXTS.create).heading}</DialogTitle>
          <DialogDescription>제목은 꼭 필요하고, 설명은 비워 두어도 됩니다.</DialogDescription>
        </DialogHeader>
        <ProjectForm onSubmit={onSubmit} onClose={() => onOpenChange(false)} project={project} />
      </DialogContent>
    </Dialog>
  )
}
