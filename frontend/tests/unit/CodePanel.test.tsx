import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CodePanel, type CodePanelFile } from '../../src/components/document/CodePanel'
import type { MonacoEditorProps } from '../../src/components/document/MonacoEditor'

// Monaco cannot run in jsdom: the editor is replaced by a stand-in that shows
// what it was given and lets the test report a scroll.
let lastEditor: MonacoEditorProps
vi.mock('../../src/components/document/LazyCodeEditor', () => ({
  LazyCodeEditor: (props: MonacoEditorProps) => {
    lastEditor = props
    return (
      <div
        data-testid="editor"
        data-path={props.path}
        data-language={props.language}
        data-highlight={props.highlight ? `${props.highlight.start}-${props.highlight.end}` : ''}
      >
        {props.value}
      </div>
    )
  },
}))

const APP: CodePanelFile = { filePath: 'src/app.py', language: 'python', content: 'print(1)\n' }
const STYLE: CodePanelFile = { filePath: 'src/style.css', language: 'css', content: 'a {}\n' }
const NOTES: CodePanelFile = { filePath: 'notes.txt', language: 'text', content: 'memo\n' }

describe('CodePanel', () => {
  it('shows a single file without tabs, named by its path', () => {
    render(<CodePanel files={[APP]} />)
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    expect(screen.getByText('src/app.py')).toBeInTheDocument()
    const editor = screen.getByTestId('editor')
    expect(editor).toHaveAttribute('data-path', 'src/app.py')
    expect(editor).toHaveAttribute('data-language', 'python')
    expect(editor).toHaveTextContent('print(1)')
  })

  it('gives the editor an accessible name', () => {
    render(<CodePanel files={[APP]} />)
    expect(lastEditor.label).toBe('src/app.py 코드')
    expect(screen.getByRole('region', { name: '코드' })).toBeInTheDocument()
  })

  it('shows file tabs when there are several files and switches between them', async () => {
    render(<CodePanel files={[APP, STYLE]} />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map((tab) => tab.textContent)).toEqual(['src/app.py', 'src/style.css'])
    expect(screen.getByRole('tablist', { name: '코드 파일' })).toBeInTheDocument()
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')

    await userEvent.click(tabs[1])
    expect(screen.getByRole('tab', { name: 'src/style.css' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    const editor = screen.getByTestId('editor')
    expect(editor).toHaveAttribute('data-path', 'src/style.css')
    expect(editor).toHaveAttribute('data-language', 'css')
  })

  it.each([
    ['python', 'python'],
    ['typescript', 'typescript'],
    ['cpp', 'cpp'],
    ['text', 'plaintext'],
    ['unknown-lang', 'plaintext'],
  ])('maps the file language %s to the Monaco language %s', (language, monacoLanguage) => {
    render(<CodePanel files={[{ ...NOTES, language }]} />)
    expect(screen.getByTestId('editor')).toHaveAttribute('data-language', monacoLanguage)
  })

  it('highlights the line range when it belongs to the shown file', () => {
    render(
      <CodePanel
        files={[APP, STYLE]}
        highlight={{ filePath: 'src/app.py', lineStart: 3, lineEnd: 5 }}
      />,
    )
    expect(screen.getByTestId('editor')).toHaveAttribute('data-highlight', '3-5')
  })

  it('switches to the file of a highlight that points to another file', () => {
    const { rerender } = render(<CodePanel files={[APP, STYLE]} />)
    expect(screen.getByTestId('editor')).toHaveAttribute('data-path', 'src/app.py')
    rerender(
      <CodePanel
        files={[APP, STYLE]}
        highlight={{ filePath: 'src/style.css', lineStart: 1, lineEnd: 1 }}
      />,
    )
    const editor = screen.getByTestId('editor')
    expect(editor).toHaveAttribute('data-path', 'src/style.css')
    expect(editor).toHaveAttribute('data-highlight', '1-1')
  })

  it('does not highlight while another file is shown', async () => {
    render(
      <CodePanel
        files={[APP, STYLE]}
        highlight={{ filePath: 'src/app.py', lineStart: 2, lineEnd: 2 }}
      />,
    )
    await userEvent.click(screen.getByRole('tab', { name: 'src/style.css' }))
    expect(screen.getByTestId('editor')).toHaveAttribute('data-highlight', '')
  })

  it('reports the top visible line together with the file path', () => {
    const onTopLineChange = vi.fn()
    render(<CodePanel files={[APP]} onTopLineChange={onTopLineChange} />)
    lastEditor.onTopLineChange(7)
    expect(onTopLineChange).toHaveBeenCalledWith('src/app.py', 7)
  })

  it('says so when there is no code', () => {
    render(<CodePanel files={[]} />)
    expect(screen.getByText('표시할 코드 파일이 없습니다.')).toBeInTheDocument()
    expect(screen.queryByTestId('editor')).not.toBeInTheDocument()
  })
})
