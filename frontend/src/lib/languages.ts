// Languages the backend knows (SUPPORTED_LANGUAGES) with their Korean labels.
export const LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'html', label: 'HTML' },
  { value: 'css', label: 'CSS' },
  { value: 'java', label: 'Java' },
  { value: 'c', label: 'C' },
  { value: 'cpp', label: 'C++' },
  { value: 'markdown', label: 'Markdown' },
  { value: 'text', label: '일반 텍스트' },
] as const

export type Language = (typeof LANGUAGES)[number]['value']

/** Display name of a detected language; unknown values are shown as they are. */
export function languageLabel(value: string): string {
  return LANGUAGES.find((language) => language.value === value)?.label ?? value
}
