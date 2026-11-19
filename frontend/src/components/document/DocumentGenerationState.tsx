import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

const FALLBACK_ERROR = '학습 문서를 만드는 중 오류가 발생했습니다. 다시 시도하세요.'

/** "약 N분 남음"; under a minute it says "1분 이내". */
function formatRemaining(seconds: number): string {
  return seconds < 60 ? '1분 이내' : `약 ${Math.ceil(seconds / 60)}분 남음`
}

export function GeneratingState({ secondsRemaining }: { secondsRemaining: number | null }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3 rounded-lg border p-6 text-center">
      <p className="text-lg font-semibold">
        <span aria-hidden="true">⏳ </span>학습 문서 생성 중...
      </p>
      <p className="text-sm text-muted-foreground">
        AI가 코드를 분석하고 초보자용 설명을 작성하고 있습니다.
      </p>
      <div
        role="progressbar"
        aria-label="학습 문서 생성 진행 상황"
        aria-busy="true"
        className="relative mx-auto h-2 w-full max-w-sm overflow-hidden rounded bg-muted"
      >
        <div className="absolute inset-y-0 w-1/3 animate-pulse rounded bg-primary" />
      </div>
      {secondsRemaining !== null && <p className="text-sm">{formatRemaining(secondsRemaining)}</p>}
    </div>
  )
}

interface FailedProps {
  /** Korean message from the server. */
  message: string | undefined
  onRegenerate: () => void
  regenerating: boolean
  /** Why starting again was refused, if it was. */
  regenerateError: string | undefined
}

export function FailedState({ message, onRegenerate, regenerating, regenerateError }: FailedProps) {
  return (
    <div className="space-y-3">
      <Alert variant="destructive">{message || FALLBACK_ERROR}</Alert>
      {regenerateError && <p className="text-sm text-destructive">{regenerateError}</p>}
      <Button type="button" onClick={onRegenerate} disabled={regenerating}>
        {regenerating ? '다시 만드는 중…' : '다시 만들기'}
      </Button>
    </div>
  )
}
