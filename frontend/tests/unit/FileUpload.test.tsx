import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import FileUpload from '../../src/components/upload/FileUpload'

const file = (name: string) => new File(['print(1)'], name, { type: 'text/plain' })

function renderUpload(files: File[] = [], onFilesChange = vi.fn()) {
  render(<FileUpload files={files} onFilesChange={onFilesChange} />)
  return { onFilesChange }
}

describe('FileUpload', () => {
  it('has a real multiple-file input with a label', () => {
    renderUpload()
    const input = screen.getByLabelText(/파일 선택/)
    expect(input).toHaveAttribute('type', 'file')
    expect(input).toHaveAttribute('multiple')
  })

  it('explains drag and drop', () => {
    renderUpload()
    expect(screen.getByText(/끌어다 놓/)).toBeInTheDocument()
  })

  it('reports files chosen with the picker', async () => {
    const { onFilesChange } = renderUpload()
    const files = [file('a.py'), file('b.js')]
    await userEvent.upload(screen.getByLabelText(/파일 선택/), files)
    expect(onFilesChange).toHaveBeenCalledWith(files)
  })

  it('reports files dropped on the area', () => {
    const { onFilesChange } = renderUpload()
    const files = [file('a.py'), file('b.js')]
    fireEvent.drop(screen.getByTestId('file-drop-area'), { dataTransfer: { files } })
    expect(onFilesChange).toHaveBeenCalledWith(files)
  })

  it('highlights the area while a file is dragged over it', () => {
    renderUpload()
    const area = screen.getByTestId('file-drop-area')
    fireEvent.dragOver(area, { dataTransfer: { files: [] } })
    expect(area).toHaveAttribute('data-dragging', 'true')
    fireEvent.dragLeave(area)
    expect(area).toHaveAttribute('data-dragging', 'false')
  })

  it('lists the selected files', () => {
    renderUpload([file('a.py'), file('b.js')])
    const list = screen.getByRole('list', { name: '선택한 파일' })
    expect(list).toHaveTextContent('a.py')
    expect(list).toHaveTextContent('b.js')
  })

  it('shows no list when nothing is selected', () => {
    renderUpload()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })
})
