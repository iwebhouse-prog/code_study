import type { ReactNode } from 'react'

interface Props {
  number: number
  title: string
  children: ReactNode
}

/** Frame shared by every chapter: numbered heading and spacing. */
export function ChapterSection({ number, title, children }: Props) {
  return (
    <section
      data-chapter={number}
      aria-labelledby={`chapter-${number}-title`}
      className="space-y-3"
    >
      <h3 id={`chapter-${number}-title`} className="text-lg font-semibold">
        {number}. {title}
      </h3>
      {children}
    </section>
  )
}
