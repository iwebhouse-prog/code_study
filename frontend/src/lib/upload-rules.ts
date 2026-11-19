// Upload limits checked in the browser first; the backend stays the authority
// (contracts/tasks-api.md, backend T064).
export const ALLOWED_EXTENSIONS = [
  '.py',
  '.js',
  '.ts',
  '.jsx',
  '.tsx',
  '.html',
  '.css',
  '.java',
  '.cpp',
  '.c',
  '.txt',
  '.md',
] as const
export const MAX_FILES = 20
export const MAX_TOTAL_BYTES = 10 * 1024 * 1024

/** A file to upload and the path it is stored under (relative path for folders). */
export interface UploadEntry {
  file: File
  path: string
}

// FR-017: folders that are never uploaded.
const EXCLUDED_FOLDERS = ['.git', 'node_modules', '__pycache__']
const EXCLUDED_FILES = ['.DS_Store']

/** The FR-017 name that excludes this path, or undefined when the path is kept. */
export function excludedName(path: string): string | undefined {
  const parts = path.split('/')
  const folder = parts.slice(0, -1).find((part) => EXCLUDED_FOLDERS.includes(part))
  if (folder) return folder
  return EXCLUDED_FILES.find((name) => name === parts[parts.length - 1])
}

export function extensionOf(fileName: string): string {
  const dot = fileName.lastIndexOf('.')
  return dot < 0 ? '' : fileName.slice(dot).toLowerCase()
}

/** Korean message for the first problem found in the upload, or undefined. */
export function checkUpload(entries: UploadEntry[]): string | undefined {
  if (entries.length === 0) return '업로드할 파일이 없습니다.'
  if (entries.length > MAX_FILES) return '한 번에 최대 20개 파일까지 업로드할 수 있습니다.'
  const total = entries.reduce((sum, { file }) => sum + file.size, 0)
  if (total > MAX_TOTAL_BYTES) return '파일 크기가 10MB를 초과합니다.'
  const unsupported = entries.find(
    ({ path }) => !(ALLOWED_EXTENSIONS as readonly string[]).includes(extensionOf(path)),
  )
  if (unsupported) return `지원하지 않는 파일 형식입니다. (${unsupported.path})`
  return undefined
}
