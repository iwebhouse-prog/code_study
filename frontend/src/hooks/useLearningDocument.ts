import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { taskDocumentKey, taskDocumentStatusKey } from '@/lib/query-keys'
import { documentService, type DocumentStatus } from '@/services/document-service'

export const POLL_INTERVAL_MS = 3000

const isGenerating = (status: DocumentStatus | undefined) =>
  status?.status === 'pending' || status?.status === 'in_progress'

/**
 * Status of a task's learning document, polled while it is being generated,
 * the document itself once it is completed, and a way to start it again
 * after a failure.
 */
export function useLearningDocument(taskId: string) {
  const queryClient = useQueryClient()

  const status = useQuery({
    queryKey: taskDocumentStatusKey(taskId),
    queryFn: () => documentService.getStatus(taskId),
    // Coming back to the page must ask again: generation goes on while away.
    staleTime: 0,
    refetchInterval: (query) => (isGenerating(query.state.data) ? POLL_INTERVAL_MS : false),
  })

  const document = useQuery({
    queryKey: taskDocumentKey(taskId),
    queryFn: () => documentService.getDocument(taskId),
    enabled: status.data?.status === 'completed',
  })

  const regenerate = useMutation({
    mutationFn: () => documentService.regenerate(taskId),
    onSuccess: (pending) => {
      queryClient.setQueryData(taskDocumentStatusKey(taskId), pending)
    },
  })

  return { status, document, regenerate }
}
