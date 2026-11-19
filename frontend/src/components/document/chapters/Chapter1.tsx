import type { Chapter1 as Chapter1Content } from '@/services/document-types'
import { ChapterSection } from '../ChapterSection'

export function Chapter1({ chapter }: { chapter: Chapter1Content }) {
  return (
    <ChapterSection number={1} title={chapter.title}>
      <p>{chapter.summary}</p>
    </ChapterSection>
  )
}
