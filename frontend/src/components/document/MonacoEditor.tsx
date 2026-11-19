import Editor, { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import { useEffect, useRef, useState } from 'react'

// Use the bundled Monaco instead of the CDN copy the loader fetches by default.
loader.config({ monaco })

// Monaco 0.57 starts its web workers from `new URL(..., import.meta.url)`, which Vite
// bundles as separate files that are only fetched when a worker is needed.

export interface LineRange {
  start: number
  end: number
}

export interface MonacoEditorProps {
  /** Unique per file, so Monaco keeps one model (and scroll position) per file. */
  path: string
  /** Monaco language id. */
  language: string
  value: string
  /** Lines to mark and scroll into view; a new object scrolls again. */
  highlight: LineRange | null
  /** Called with the first visible line when the user scrolls. */
  onTopLineChange: (line: number) => void
  /** Accessible name of the editor. */
  label: string
}

const HIGHLIGHT_CLASS = 'code-highlight-line'

export default function MonacoEditor({
  path,
  language,
  value,
  highlight,
  onTopLineChange,
  label,
}: MonacoEditorProps) {
  const [editor, setEditor] = useState<monaco.editor.IStandaloneCodeEditor | null>(null)
  const decorationsRef = useRef<monaco.editor.IEditorDecorationsCollection | null>(null)
  const programmaticScrollRef = useRef(false)
  const onTopLineChangeRef = useRef(onTopLineChange)

  useEffect(() => {
    onTopLineChangeRef.current = onTopLineChange
  }, [onTopLineChange])

  useEffect(() => {
    if (!editor) return
    decorationsRef.current?.clear()
    decorationsRef.current = null
    if (!highlight) return
    decorationsRef.current = editor.createDecorationsCollection([
      {
        range: new monaco.Range(highlight.start, 1, highlight.end, 1),
        options: { isWholeLine: true, className: HIGHLIGHT_CLASS },
      },
    ])
    // Scroll events caused by this reveal must not be reported as user scrolling.
    programmaticScrollRef.current = true
    editor.revealLinesInCenterIfOutsideViewport(
      highlight.start,
      highlight.end,
      monaco.editor.ScrollType.Immediate,
    )
    programmaticScrollRef.current = false
  }, [editor, highlight, path])

  return (
    <Editor
      path={path}
      language={language}
      value={value}
      height="100%"
      theme="vs"
      options={{
        readOnly: true,
        domReadOnly: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        automaticLayout: true,
        ariaLabel: label,
      }}
      onMount={(editor) => {
        setEditor(editor)
        editor.onDidScrollChange(() => {
          if (programmaticScrollRef.current) return
          const top = editor.getVisibleRanges()[0]?.startLineNumber
          if (top !== undefined) onTopLineChangeRef.current(top)
        })
      }}
    />
  )
}
