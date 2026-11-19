import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import FolderUpload from '../../src/components/upload/FolderUpload'

function entry(path: string) {
  const file = new File(['x'], path.split('/').pop() ?? path)
  Object.defineProperty(file, 'webkitRelativePath', { value: path })
  return file
}

function pick(paths: string[]) {
  const onChange = vi.fn()
  render(<FolderUpload entries={[]} onChange={onChange} />)
  fireEvent.change(screen.getByLabelText(/폴더 선택/), {
    target: { files: paths.map(entry) },
  })
  return onChange
}

describe('FolderUpload', () => {
  it('has a directory input with a label', () => {
    render(<FolderUpload entries={[]} onChange={vi.fn()} />)
    expect(screen.getByLabelText(/폴더 선택/)).toHaveAttribute('webkitdirectory')
  })

  it('keeps webkitRelativePath as the path of every file', () => {
    const onChange = pick(['app/src/App.jsx', 'app/index.html'])
    const entries = onChange.mock.calls[0][0]
    expect(entries.map((e: { path: string }) => e.path)).toEqual([
      'app/src/App.jsx',
      'app/index.html',
    ])
    expect(entries[0].file.name).toBe('App.jsx')
  })

  it.each([
    'app/.git/config',
    'app/node_modules/react/index.js',
    'app/__pycache__/a.pyc',
    'app/.DS_Store',
  ])('drops %s', (path) => {
    const onChange = pick(['app/main.py', path])
    expect(onChange.mock.calls[0][0].map((e: { path: string }) => e.path)).toEqual(['app/main.py'])
  })

  it('names only the excluded folders that occurred', () => {
    pick(['app/main.py', 'app/.git/config', 'app/node_modules/a.js', 'app/node_modules/b.js'])
    expect(screen.getByText('제외된 폴더: .git, node_modules')).toBeInTheDocument()
  })

  it('shows no message when nothing was excluded', () => {
    pick(['app/main.py'])
    expect(screen.queryByText(/제외된 폴더/)).not.toBeInTheDocument()
  })

  it('lists the kept files', () => {
    render(
      <FolderUpload entries={[{ file: entry('app/a.py'), path: 'app/a.py' }]} onChange={vi.fn()} />,
    )
    expect(screen.getByRole('list', { name: '선택한 파일' })).toHaveTextContent('app/a.py')
  })
})
