import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Alert } from '@/components/ui/alert'
import { useLearningDocument } from '@/hooks/useLearningDocument'
import { taskCodeKey } from '@/lib/query-keys'
import type { DocumentContent } from '@/services/document-types'
import { taskService } from '@/services/task-service'
import { CodePanel, type CodeHighlight } from './CodePanel'
import { FailedState, GeneratingState } from './DocumentGenerationState'
import { ExplanationPanel } from './ExplanationPanel'

function Loading({ children }: { children: string }) {
  return (
    <p role="status" className="text-muted-foreground">
      {children}
    </p>
  )
}

/** Code on the left, explanation on the right (stacked on narrow screens), linked by line. */
function DocumentColumns({ taskId, content }: { taskId: string; content: DocumentContent }) {
  const code = useQuery({
    queryKey: taskCodeKey(taskId),
    queryFn: () => taskService.getCode(taskId),
  })
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [highlight, setHighlight] = useState<CodeHighlight | null>(null)
  const explanations = content.chapter4.explanations

  const files = useMemo(
    () =>
      (code.data?.files ?? []).map((file) => ({
        filePath: file.filePath,
        language: file.language,
        content: file.content,
      })),
    [code.data],
  )

  function selectExplanation(index: number) {
    const item = explanations[index]
    setActiveIndex(index)
    setHighlight({ filePath: item.filePath, lineStart: item.lineStart, lineEnd: item.lineEnd })
  }

  // The code scrolled: follow it with the explanation that covers the top line.
  function codeScrolled(filePath: string, line: number) {
    const index = explanations.findIndex(
      (item) => item.filePath === filePath && item.lineStart <= line && line <= item.lineEnd,
    )
    if (index !== -1) setActiveIndex(index)
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:h-[75vh] lg:grid-cols-2">
      {code.isPending && <Loading>코드를 불러오는 중입니다…</Loading>}
      {code.isError && <Alert variant="destructive">{code.error.message}</Alert>}
      {code.isSuccess && (
        <CodePanel files={files} highlight={highlight} onTopLineChange={codeScrolled} />
      )}
      <ExplanationPanel
        content={content}
        activeExplanationIndex={activeIndex}
        onSelectExplanation={selectExplanation}
      />
    </div>
  )
}

export function DocumentViewer({ taskId }: { taskId: string }) {
  const { status, document, regenerate } = useLearningDocument(taskId)

  if (status.isPending) return <Loading>학습 문서 상태를 확인하는 중입니다…</Loading>
  if (status.isError) return <Alert variant="destructive">{status.error.message}</Alert>

  const { status: state, estimatedSecondsRemaining, error } = status.data
  if (state === 'pending' || state === 'in_progress') {
    return <GeneratingState secondsRemaining={estimatedSecondsRemaining} />
  }
  if (state === 'failed') {
    return (
      <FailedState
        message={error?.message}
        onRegenerate={() => regenerate.mutate()}
        regenerating={regenerate.isPending}
        regenerateError={regenerate.error?.message}
      />
    )
  }

  if (document.isPending) return <Loading>학습 문서를 불러오는 중입니다…</Loading>
  if (document.isError) return <Alert variant="destructive">{document.error.message}</Alert>
  return <DocumentColumns taskId={taskId} content={document.data.content} />
}
