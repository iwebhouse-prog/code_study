import { useQueryClient } from '@tanstack/react-query'
import { useId, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import FileUpload from '@/components/upload/FileUpload'
import FolderUpload from '@/components/upload/FolderUpload'
import PasteCode from '@/components/upload/PasteCode'
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
import { Tabs } from '@/components/ui/tabs'
import type { Language } from '@/lib/languages'
import { paths } from '@/lib/paths'
import { PROJECTS_KEY } from '@/lib/query-keys'
import { checkUpload, type UploadEntry } from '@/lib/upload-rules'
import { ApiError } from '@/services/api-client'
import { taskService, type NewTask, type UploadResult } from '@/services/task-service'
import { useToastStore } from '@/stores/toast-store'

const TITLE_MIN_LENGTH = 5
const TITLE_MAX_LENGTH = 255
const DESCRIPTION_MAX_LENGTH = 500

const TABS = [
  { id: 'file', label: '파일 업로드' },
  { id: 'folder', label: '폴더 업로드' },
  { id: 'paste', label: '코드 붙여넣기' },
] as const

type UploadTab = (typeof TABS)[number]['id']

interface FieldErrors {
  title?: string
  description?: string
  upload?: string
  code?: string
  language?: string
}

const FALLBACK_ERROR = '태스크를 만들지 못했습니다. 잠시 후 다시 시도하세요.'

// Same rules and messages as the backend; this only saves a round trip, the
// server's answer is final.
function checkTitle(title: string): string | undefined {
  if (title.length < TITLE_MIN_LENGTH) return '태스크 제목은 최소 5자 이상이어야 합니다.'
  if (title.length > TITLE_MAX_LENGTH) return '태스크 제목은 최대 255자까지 입력할 수 있습니다.'
  return undefined
}

function checkDescription(description: string): string | undefined {
  return description.length > DESCRIPTION_MAX_LENGTH
    ? '태스크 설명은 최대 500자까지 입력할 수 있습니다.'
    : undefined
}

function ErrorText({ id, children }: { id: string; children?: string }) {
  if (!children) return null
  return (
    <p id={id} className="text-sm text-destructive">
      {children}
    </p>
  )
}

function Confirmation({
  result,
  onClose,
  onView,
}: {
  result: UploadResult
  onClose: () => void
  onView: () => void
}) {
  return (
    <>
      <DialogHeader>
        <DialogTitle>업로드 완료</DialogTitle>
        <DialogDescription>
          Task {result.taskNumber}. {result.title} 태스크가 만들어졌습니다.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-4 text-sm">
        <ul aria-label="업로드한 파일" className="space-y-1">
          {result.files.map((file) => (
            <li key={file.id}>{file.filePath}</li>
          ))}
        </ul>
        {result.excludedPaths.length > 0 && (
          <div className="space-y-1">
            <p className="text-muted-foreground">다음 파일은 제외되었습니다.</p>
            <ul aria-label="제외된 파일" className="space-y-1">
              {result.excludedPaths.map((path) => (
                <li key={path}>{path}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          닫기
        </Button>
        <Button type="button" onClick={onView}>
          태스크 보기
        </Button>
      </DialogFooter>
    </>
  )
}

function TaskFlow({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const id = useId()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const showToast = useToastStore((state) => state.show)

  const [tab, setTab] = useState<UploadTab>('file')
  const [files, setFiles] = useState<File[]>([])
  const [folderEntries, setFolderEntries] = useState<UploadEntry[]>([])
  const [code, setCode] = useState('')
  const [language, setLanguage] = useState<Language | ''>('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<ApiError | string>()
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState<UploadResult>()

  function validate(title: string, description: string): FieldErrors {
    const found: FieldErrors = {
      title: checkTitle(title),
      description: checkDescription(description),
    }
    if (tab === 'paste') {
      if (!code.trim()) found.code = '붙여넣을 코드를 입력하세요.'
      if (!language) found.language = '프로그래밍 언어를 선택하세요.'
    } else {
      const entries =
        tab === 'file' ? files.map((file) => ({ file, path: file.name })) : folderEntries
      found.upload = checkUpload(entries)
    }
    return found
  }

  function buildTask(title: string, description: string): NewTask {
    const base = description ? { title, description } : { title }
    if (tab === 'paste')
      return { ...base, uploadMethod: 'paste', code, language: language as Language }
    const entries =
      tab === 'file' ? files.map((file) => ({ file, path: file.name })) : folderEntries
    return { ...base, uploadMethod: tab, files: entries }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const title = String(data.get('title')).trim()
    const description = String(data.get('description')).trim()

    const found = validate(title, description)
    setFormError(undefined)
    setErrors(found)
    if (Object.values(found).some(Boolean)) return

    setPending(true)
    try {
      const created = await taskService.create(projectId, buildTask(title, description))
      // 'projects' is the prefix of the project, its task list and the project list.
      void queryClient.invalidateQueries({ queryKey: PROJECTS_KEY })
      showToast('태스크가 생성되었습니다.')
      setResult(created)
    } catch (error) {
      if (error instanceof ApiError) {
        const fields = error.fieldErrors
        const shown = {
          title: fields.title,
          description: fields.description,
          code: fields.code,
          language: fields.language,
        }
        setErrors(shown)
        setFormError(Object.values(shown).some(Boolean) ? undefined : error)
      } else {
        setFormError(FALLBACK_ERROR)
      }
    } finally {
      setPending(false)
    }
  }

  if (result) {
    return (
      <Confirmation
        result={result}
        onClose={onClose}
        onView={() => {
          onClose()
          navigate(paths.task(result.id))
        }}
      />
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>새 태스크</DialogTitle>
        <DialogDescription>
          제목을 적고 학습할 코드를 파일, 폴더, 붙여넣기 중 하나로 올리세요.
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        {formError && (
          <Alert variant="destructive">
            {typeof formError === 'string' ? (
              formError
            ) : (
              <>
                <p>{formError.message}</p>
                {formError.suggestion && <p>{formError.suggestion}</p>}
              </>
            )}
          </Alert>
        )}
        <div className="space-y-2">
          <Label htmlFor={`${id}-title`}>태스크 제목</Label>
          <Input
            id={`${id}-title`}
            name="title"
            required
            aria-invalid={errors.title ? true : undefined}
            aria-describedby={errors.title ? `${id}-title-error` : undefined}
          />
          <ErrorText id={`${id}-title-error`}>{errors.title}</ErrorText>
        </div>
        <div className="space-y-2">
          <Label htmlFor={`${id}-description`}>설명 (선택)</Label>
          <Input
            id={`${id}-description`}
            name="description"
            aria-invalid={errors.description ? true : undefined}
            aria-describedby={errors.description ? `${id}-description-error` : undefined}
          />
          <ErrorText id={`${id}-description-error`}>{errors.description}</ErrorText>
        </div>
        <Tabs label="업로드 방법" tabs={TABS} value={tab} onValueChange={setTab}>
          {tab === 'file' && (
            <FileUpload files={files} onFilesChange={setFiles} disabled={pending} />
          )}
          {tab === 'folder' && (
            <FolderUpload entries={folderEntries} onChange={setFolderEntries} disabled={pending} />
          )}
          {tab === 'paste' && (
            <PasteCode
              code={code}
              language={language}
              onCodeChange={setCode}
              onLanguageChange={setLanguage}
              codeError={errors.code}
              languageError={errors.language}
            />
          )}
          {tab !== 'paste' && <ErrorText id={`${id}-upload-error`}>{errors.upload}</ErrorText>}
        </Tabs>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            취소
          </Button>
          <Button type="submit" disabled={pending}>
            {pending ? '만드는 중…' : '태스크 만들기'}
          </Button>
        </DialogFooter>
      </form>
    </>
  )
}

interface Props {
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export default function CreateTaskModal({ projectId, open, onOpenChange }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <TaskFlow projectId={projectId} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  )
}
