import { lazy, Suspense } from 'react'
import type { MonacoEditorProps } from './MonacoEditor'

// Monaco is large: it is fetched as its own chunk when the first editor shows.
const MonacoEditor = lazy(() => import('./MonacoEditor'))

export function LazyCodeEditor(props: MonacoEditorProps) {
  return (
    <Suspense
      fallback={
        <p role="status" className="p-4 text-sm text-muted-foreground">
          코드 편집기를 불러오는 중입니다…
        </p>
      }
    >
      <MonacoEditor {...props} />
    </Suspense>
  )
}
