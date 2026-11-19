import { useMemo, useState } from 'react'
import { Tabs } from '@/components/ui/tabs'
import { LazyCodeEditor } from './LazyCodeEditor'

export interface CodePanelFile {
  filePath: string
  /** Language name the backend detected (see lib/languages.ts). */
  language: string
  content: string
}

export interface CodeHighlight {
  filePath: string
  lineStart: number
  lineEnd: number
}

interface Props {
  files: readonly CodePanelFile[]
  highlight?: CodeHighlight | null
  /** The user scrolled: first visible line of the shown file. */
  onTopLineChange?: (filePath: string, line: number) => void
}

// Languages Monaco calls by another name; the rest share the backend's names.
const MONACO_LANGUAGES: Record<string, string> = {
  python: 'python',
  javascript: 'javascript',
  typescript: 'typescript',
  html: 'html',
  css: 'css',
  java: 'java',
  c: 'c',
  cpp: 'cpp',
  markdown: 'markdown',
}

export function CodePanel({ files, highlight = null, onTopLineChange }: Props) {
  const [activePath, setActivePath] = useState(files[0]?.filePath)
  const [seenHighlight, setSeenHighlight] = useState(highlight)

  // A new highlight in another file opens that file (state adjusted while rendering).
  if (highlight !== seenHighlight) {
    setSeenHighlight(highlight)
    if (highlight && files.some((file) => file.filePath === highlight.filePath)) {
      setActivePath(highlight.filePath)
    }
  }

  const active = files.find((file) => file.filePath === activePath) ?? files[0]
  const range = useMemo(
    () =>
      highlight && active && highlight.filePath === active.filePath
        ? { start: highlight.lineStart, end: highlight.lineEnd }
        : null,
    [highlight, active],
  )

  if (!active) {
    return (
      <section aria-label="코드" className="text-sm text-muted-foreground">
        표시할 코드 파일이 없습니다.
      </section>
    )
  }

  const editor = (
    <div className="h-[24rem] lg:h-full">
      <LazyCodeEditor
        path={active.filePath}
        language={MONACO_LANGUAGES[active.language] ?? 'plaintext'}
        value={active.content}
        highlight={range}
        label={`${active.filePath} 코드`}
        onTopLineChange={(line) => onTopLineChange?.(active.filePath, line)}
      />
    </div>
  )

  return (
    <section aria-label="코드" className="space-y-2">
      {files.length > 1 ? (
        <Tabs
          label="코드 파일"
          tabs={files.map((file) => ({ id: file.filePath, label: file.filePath }))}
          value={active.filePath}
          onValueChange={setActivePath}
        >
          {editor}
        </Tabs>
      ) : (
        <>
          <p className="font-mono text-sm text-muted-foreground">{active.filePath}</p>
          {editor}
        </>
      )}
    </section>
  )
}
