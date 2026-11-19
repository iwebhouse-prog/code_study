import type { Chapter2 as Chapter2Content } from '@/services/document-types'
import { ChapterSection } from '../ChapterSection'

function Field({ label, children }: { label: string; children: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

export function Chapter2({ chapter }: { chapter: Chapter2Content }) {
  return (
    <ChapterSection number={2} title={chapter.title}>
      <ul className="space-y-3">
        {chapter.concepts.map((concept) => (
          <li key={concept.name} className="space-y-2 rounded-lg border p-4">
            <h4 className="font-medium">{concept.name}</h4>
            <dl className="space-y-2 text-sm">
              <Field label="쉬운 설명">{concept.explanation}</Field>
              <Field label="비유">{concept.analogy}</Field>
              <div>
                <dt className="text-xs font-medium text-muted-foreground">예시</dt>
                <dd>
                  <pre className="overflow-x-auto rounded bg-muted p-2 font-mono text-xs">
                    <code>{concept.example}</code>
                  </pre>
                </dd>
              </div>
              <Field label="자주 쓰이는 곳">{concept.useCases}</Field>
            </dl>
          </li>
        ))}
      </ul>
    </ChapterSection>
  )
}
