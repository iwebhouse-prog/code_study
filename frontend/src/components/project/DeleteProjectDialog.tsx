import { useState } from 'react'
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
import { ApiError } from '@/services/api-client'

const UNEXPECTED_ERROR_MESSAGE = '프로젝트를 삭제하지 못했습니다. 잠시 후 다시 시도하세요.'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectTitle: string
  /** Deletes the project; a rejection keeps the dialog open and is shown in it. */
  onConfirm: () => Promise<void>
}

function DeleteProjectBody({
  projectTitle,
  onConfirm,
  onClose,
}: Omit<Props, 'open' | 'onOpenChange'> & { onClose: () => void }) {
  const [error, setError] = useState<string>()
  const [pending, setPending] = useState(false)

  async function handleConfirm() {
    setError(undefined)
    setPending(true)
    try {
      await onConfirm()
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : UNEXPECTED_ERROR_MESSAGE)
      setPending(false)
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>프로젝트를 삭제할까요?</DialogTitle>
        <DialogDescription>
          &apos;{projectTitle}&apos; 프로젝트는 휴지통으로 이동하며, 30일 안에는 복구할 수 있습니다.
        </DialogDescription>
      </DialogHeader>
      {error && <Alert variant="destructive">{error}</Alert>}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          취소
        </Button>
        <Button type="button" variant="destructive" disabled={pending} onClick={handleConfirm}>
          {pending ? '삭제하는 중…' : '삭제'}
        </Button>
      </DialogFooter>
    </>
  )
}

// A confirmation inside the page (never window.confirm), so it can be styled,
// tested and read by screen readers like the rest of the app.
export default function DeleteProjectDialog({
  open,
  onOpenChange,
  projectTitle,
  onConfirm,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent role="alertdialog">
        <DeleteProjectBody
          projectTitle={projectTitle}
          onConfirm={onConfirm}
          onClose={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  )
}
