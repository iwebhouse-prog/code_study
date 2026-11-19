import { useId, useState, type ChangeEvent, type DragEvent } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  files: File[]
  onFilesChange: (files: File[]) => void
  disabled?: boolean
}

export default function FileUpload({ files, onFilesChange, disabled }: Props) {
  const id = useId()
  const [dragging, setDragging] = useState(false)

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onFilesChange(Array.from(event.target.files ?? []))
  }

  function handleDragOver(event: DragEvent) {
    event.preventDefault()
    setDragging(true)
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    onFilesChange(Array.from(event.dataTransfer.files))
  }

  return (
    <div className="space-y-2">
      {/* The label wraps a real file input, so click and keyboard both open the picker. */}
      <label
        data-testid="file-drop-area"
        data-dragging={dragging}
        onDragOver={handleDragOver}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        htmlFor={id}
        className={cn(
          'flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-dashed p-6 text-center text-sm text-muted-foreground focus-within:ring-2 focus-within:ring-ring',
          dragging && 'border-primary bg-accent',
        )}
      >
        <span>
          <span className="sr-only">파일 선택: </span>
          파일을 여기로 끌어다 놓거나 클릭하여 선택하세요.
        </span>
        <span>여러 개를 한 번에 올릴 수 있습니다.</span>
        <input
          id={id}
          type="file"
          multiple
          disabled={disabled}
          onChange={handleChange}
          className="sr-only"
        />
      </label>
      {files.length > 0 && (
        <ul aria-label="선택한 파일" className="space-y-1 text-sm">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`}>{file.name}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
