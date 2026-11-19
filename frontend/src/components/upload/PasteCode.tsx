import { useId } from 'react'
import { Label } from '@/components/ui/label'
import { LANGUAGES, type Language } from '@/lib/languages'

interface Props {
  code: string
  language: Language | ''
  onCodeChange: (code: string) => void
  onLanguageChange: (language: Language | '') => void
  codeError?: string
  languageError?: string
}

const FIELD =
  'w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

export default function PasteCode({
  code,
  language,
  onCodeChange,
  onLanguageChange,
  codeError,
  languageError,
}: Props) {
  const id = useId()
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor={`${id}-code`}>붙여넣을 코드</Label>
        <textarea
          id={`${id}-code`}
          value={code}
          onChange={(event) => onCodeChange(event.target.value)}
          rows={10}
          spellCheck={false}
          aria-invalid={codeError ? true : undefined}
          aria-describedby={codeError ? `${id}-code-error` : undefined}
          className={`${FIELD} font-mono`}
        />
        {codeError && (
          <p id={`${id}-code-error`} className="text-sm text-destructive">
            {codeError}
          </p>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${id}-language`}>프로그래밍 언어</Label>
        <select
          id={`${id}-language`}
          value={language}
          required
          onChange={(event) => onLanguageChange(event.target.value as Language | '')}
          aria-invalid={languageError ? true : undefined}
          aria-describedby={languageError ? `${id}-language-error` : undefined}
          className={FIELD}
        >
          <option value="">언어 선택</option>
          {LANGUAGES.map(({ value, label }) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        {languageError && (
          <p id={`${id}-language-error`} className="text-sm text-destructive">
            {languageError}
          </p>
        )}
      </div>
    </div>
  )
}
