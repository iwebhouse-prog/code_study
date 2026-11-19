import { useId, useState, type ChangeEvent } from 'react'
import { excludedName, type UploadEntry } from '@/lib/upload-rules'

interface Props {
  entries: UploadEntry[]
  onChange: (entries: UploadEntry[]) => void
  disabled?: boolean
}

// `webkitdirectory` is not in React's input typings yet.
const DIRECTORY_ATTRIBUTE = { webkitdirectory: '' }

export default function FolderUpload({ entries, onChange, disabled }: Props) {
  const id = useId()
  const [excluded, setExcluded] = useState<string[]>([])

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const kept: UploadEntry[] = []
    const dropped = new Set<string>()
    for (const file of Array.from(event.target.files ?? [])) {
      const path = file.webkitRelativePath || file.name
      const name = excludedName(path)
      if (name) dropped.add(name)
      else kept.push({ file, path })
    }
    setExcluded([...dropped])
    onChange(kept)
  }

  return (
    <div className="space-y-2">
      <label
        htmlFor={id}
        className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-dashed p-6 text-center text-sm text-muted-foreground focus-within:ring-2 focus-within:ring-ring"
      >
        <span>
          <span className="sr-only">폴더 선택: </span>
          클릭하여 폴더를 선택하세요. 폴더 구조가 그대로 유지됩니다.
        </span>
        <input
          id={id}
          type="file"
          disabled={disabled}
          onChange={handleChange}
          className="sr-only"
          {...DIRECTORY_ATTRIBUTE}
        />
      </label>
      {excluded.length > 0 && (
        <p className="text-sm text-muted-foreground">제외된 폴더: {excluded.join(', ')}</p>
      )}
      {entries.length > 0 && (
        <ul aria-label="선택한 파일" className="space-y-1 text-sm">
          {entries.map(({ path }) => (
            <li key={path}>{path}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
