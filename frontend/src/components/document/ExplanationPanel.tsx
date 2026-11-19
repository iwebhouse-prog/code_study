import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'
import type { DocumentContent } from '@/services/document-types'
import { Chapter1 } from './chapters/Chapter1'
import { Chapter2 } from './chapters/Chapter2'
import { Chapter4 } from './chapters/Chapter4'
import { Chapter3, Chapter5, Chapter6, Chapter7 } from './chapters/SimpleChapters'

interface Props {
  content: DocumentContent
  /** Chapter 4 item that matches the code the user is looking at. */
  activeExplanationIndex: number | null
  onSelectExplanation: (index: number) => void
}

const CHAPTER_KEYS = [
  'chapter1',
  'chapter2',
  'chapter3',
  'chapter4',
  'chapter5',
  'chapter6',
  'chapter7',
] as const

const EXPLANATION_CHAPTER = 4

// Scrolls `target` to the top of `scroller` (only the panel moves, not the page).
// With `onlyIfHidden` nothing happens while the target is fully visible.
function scrollWithin(scroller: HTMLElement, target: Element, onlyIfHidden = false) {
  const area = scroller.getBoundingClientRect()
  const box = target.getBoundingClientRect()
  if (onlyIfHidden && box.top >= area.top && box.bottom <= area.bottom) return
  scroller.scrollTo({ top: box.top - area.top + scroller.scrollTop })
}

export function ExplanationPanel({ content, activeExplanationIndex, onSelectExplanation }: Props) {
  const [current, setCurrent] = useState(1)
  const [seenIndex, setSeenIndex] = useState(activeExplanationIndex)
  const scrollerRef = useRef<HTMLDivElement>(null)

  // The code moved to a new explanation: chapter 4 becomes the current chapter.
  if (activeExplanationIndex !== seenIndex) {
    setSeenIndex(activeExplanationIndex)
    if (activeExplanationIndex !== null) setCurrent(EXPLANATION_CHAPTER)
  }

  useEffect(() => {
    const scroller = scrollerRef.current
    if (!scroller || activeExplanationIndex === null) return
    const item = scroller.querySelector(`[data-explanation-index="${activeExplanationIndex}"]`)
    if (item) scrollWithin(scroller, item, true)
  }, [activeExplanationIndex])

  function goToChapter(number: number) {
    setCurrent(number)
    const scroller = scrollerRef.current
    const section = scroller?.querySelector(`[data-chapter="${number}"]`)
    if (scroller && section) scrollWithin(scroller, section)
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <nav aria-label="챕터 이동" className="flex flex-wrap gap-1">
        {CHAPTER_KEYS.map((key, index) => {
          const number = index + 1
          const isCurrent = number === current
          return (
            <button
              key={key}
              type="button"
              aria-current={isCurrent ? 'true' : undefined}
              onClick={() => goToChapter(number)}
              className={cn(
                'rounded-md border px-2 py-1 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                isCurrent
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {number}. {content[key].title}
            </button>
          )
        })}
      </nav>
      <div
        ref={scrollerRef}
        role="region"
        aria-label="학습 문서 설명"
        tabIndex={0}
        className="min-h-0 flex-1 space-y-8 overflow-y-auto pr-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Chapter1 chapter={content.chapter1} />
        <Chapter2 chapter={content.chapter2} />
        <Chapter3 chapter={content.chapter3} />
        <Chapter4
          chapter={content.chapter4}
          activeIndex={activeExplanationIndex}
          onSelectExplanation={onSelectExplanation}
        />
        <Chapter5 chapter={content.chapter5} />
        <Chapter6 chapter={content.chapter6} />
        <Chapter7 chapter={content.chapter7} />
      </div>
    </div>
  )
}
