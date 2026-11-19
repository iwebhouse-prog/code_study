import { cn } from '@/lib/utils'
import type { Chapter4 as Chapter4Content, LineExplanation } from '@/services/document-types'
import { ChapterSection } from '../ChapterSection'

interface Props {
  chapter: Chapter4Content
  /** Item that is linked to the highlighted code lines. */
  activeIndex: number | null
  onSelectExplanation: (index: number) => void
}

function lineLabel({ lineStart, lineEnd }: LineExplanation): string {
  return lineStart === lineEnd ? `${lineStart}줄` : `${lineStart}~${lineEnd}줄`
}

function Field({ label, children }: { label: string; children: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

export function Chapter4({ chapter, activeIndex, onSelectExplanation }: Props) {
  return (
    <ChapterSection number={4} title={chapter.title}>
      <ul className="space-y-3">
        {chapter.explanations.map((item, index) => {
          const active = index === activeIndex
          return (
            <li
              key={`${item.filePath}:${item.lineStart}-${item.lineEnd}`}
              data-explanation-index={index}
              className={cn('rounded-lg border', active && 'border-primary ring-2 ring-primary')}
            >
              <button
                type="button"
                aria-pressed={active}
                onClick={() => onSelectExplanation(index)}
                className="w-full rounded-t-lg bg-muted px-4 py-2 text-left font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {item.filePath} {lineLabel(item)}
              </button>
              <div className="space-y-2 p-4 text-sm">
                <pre className="overflow-x-auto rounded bg-muted p-2 font-mono text-xs">
                  <code>{item.code}</code>
                </pre>
                <dl className="space-y-2">
                  <Field label="하는 일">{item.whatItDoes}</Field>
                  <Field label="문법 풀이">{item.syntaxBreakdown}</Field>
                  <Field label="비유">{item.analogy}</Field>
                  <Field label="다른 예시">{item.alternativeExample}</Field>
                  {item.notes && <Field label="주의할 점">{item.notes}</Field>}
                </dl>
              </div>
            </li>
          )
        })}
      </ul>
    </ChapterSection>
  )
}
