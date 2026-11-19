import type { ReactNode } from 'react'
import type {
  Chapter3 as Chapter3Content,
  Chapter5 as Chapter5Content,
  Chapter6 as Chapter6Content,
  Chapter7 as Chapter7Content,
} from '@/services/document-types'
import { ChapterSection } from '../ChapterSection'

interface Field {
  label: string
  value: string
  /** Shown as preformatted code. */
  code?: boolean
}

interface Item {
  heading: string
  fields: Field[]
}

interface Props {
  number: number
  title: string
  /** Shown above the items. */
  intro?: ReactNode
  items: Item[]
}

// Shared renderer for chapters that have no dedicated component yet:
// a list of cards, each with a heading and labelled fields.
function SimpleChapter({ number, title, intro, items }: Props) {
  return (
    <ChapterSection number={number} title={title}>
      {intro}
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.heading} className="space-y-2 rounded-lg border p-4">
            <h4 className="font-medium">{item.heading}</h4>
            <dl className="space-y-2 text-sm">
              {item.fields.map((field) => (
                <div key={field.label}>
                  <dt className="text-xs font-medium text-muted-foreground">{field.label}</dt>
                  <dd>
                    {field.code ? (
                      <pre className="overflow-x-auto rounded bg-muted p-2 font-mono text-xs">
                        <code>{field.value}</code>
                      </pre>
                    ) : (
                      field.value
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </ChapterSection>
  )
}

export function Chapter3({ chapter }: { chapter: Chapter3Content }) {
  return (
    <SimpleChapter
      number={3}
      title={chapter.title}
      // Mermaid text is shown as it is; drawing it as a diagram is not needed yet.
      intro={
        <pre className="overflow-x-auto rounded bg-muted p-2 font-mono text-xs">
          <code>{chapter.flowchart}</code>
        </pre>
      }
      items={chapter.fileBreakdown.map((file) => ({
        heading: file.filePath,
        fields: [{ label: '하는 일', value: file.role }],
      }))}
    />
  )
}

export function Chapter5({ chapter }: { chapter: Chapter5Content }) {
  return (
    <SimpleChapter
      number={5}
      title={chapter.title}
      items={chapter.steps.map((step) => ({
        heading: `단계 ${step.step}`,
        fields: [
          { label: '일어나는 일', value: step.description },
          { label: '변수 상태', value: step.dataState, code: true },
        ],
      }))}
    />
  )
}

export function Chapter6({ chapter }: { chapter: Chapter6Content }) {
  return (
    <SimpleChapter
      number={6}
      title={chapter.title}
      items={chapter.concepts.map((concept) => ({
        heading: concept.name,
        fields: [
          { label: '무엇인가요', value: concept.whatItIs },
          { label: '왜 쓰나요', value: concept.whyUsed },
          { label: '어디에 쓰나요', value: concept.whereApplied },
        ],
      }))}
    />
  )
}

export function Chapter7({ chapter }: { chapter: Chapter7Content }) {
  return (
    <SimpleChapter
      number={7}
      title={chapter.title}
      items={chapter.mistakes.map((mistake, index) => ({
        heading: `실수 ${index + 1}`,
        fields: [
          { label: '틀린 코드', value: mistake.wrong, code: true },
          { label: '고친 코드', value: mistake.right, code: true },
          { label: '왜 문제인가요', value: mistake.why },
          { label: '고치는 방법', value: mistake.fix },
        ],
      }))}
    />
  )
}
