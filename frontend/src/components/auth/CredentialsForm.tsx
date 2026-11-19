import { useId, useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '../../services/api-client'
import type { Credentials } from '../../services/auth-service'

export interface CredentialsFormProps {
  onSubmit: (credentials: Credentials) => Promise<void>
}

interface Props extends CredentialsFormProps {
  submitLabel: string
  pendingLabel: string
  passwordAutoComplete: 'current-password' | 'new-password'
  /** Returns a Korean message when the password breaks a rule, else undefined. */
  checkPassword: (password: string) => string | undefined
}

const UNEXPECTED_ERROR_MESSAGE = '문제가 발생했습니다. 잠시 후 다시 시도하세요.'
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

type FieldName = 'email' | 'password'
type FieldErrors = Partial<Record<FieldName, string>>

function checkEmail(email: string): string | undefined {
  if (!email) return '이메일을 입력하세요.'
  if (!EMAIL_PATTERN.test(email)) return '올바른 이메일 주소를 입력하세요.'
  return undefined
}

// Shared by LoginForm and RegisterForm. The checks here only save a round
// trip; whatever the server answers is final and is shown as it comes.
export default function CredentialsForm({
  onSubmit,
  submitLabel,
  pendingLabel,
  passwordAutoComplete,
  checkPassword,
}: Props) {
  const id = useId()
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string>()
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return
    const data = new FormData(event.currentTarget)
    const email = String(data.get('email')).trim()
    const password = String(data.get('password'))

    const problems: FieldErrors = { email: checkEmail(email), password: checkPassword(password) }
    setFormError(undefined)
    setFieldErrors(problems)
    if (problems.email || problems.password) return

    setPending(true)
    try {
      await onSubmit({ email, password })
    } catch (error) {
      if (error instanceof ApiError) {
        setFieldErrors(error.fieldErrors)
        setFormError(error.message)
      } else {
        setFormError(UNEXPECTED_ERROR_MESSAGE)
      }
    } finally {
      setPending(false)
    }
  }

  const fieldProps = (name: FieldName) => ({
    id: `${id}-${name}`,
    name,
    'aria-invalid': fieldErrors[name] ? true : undefined,
    'aria-describedby': fieldErrors[name] ? `${id}-${name}-error` : undefined,
  })

  const fieldError = (name: FieldName) =>
    fieldErrors[name] && (
      <p id={`${id}-${name}-error`} className="text-sm text-destructive">
        {fieldErrors[name]}
      </p>
    )

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      {formError && <Alert variant="destructive">{formError}</Alert>}
      <div className="space-y-2">
        <Label htmlFor={`${id}-email`}>이메일</Label>
        <Input type="email" autoComplete="email" {...fieldProps('email')} />
        {fieldError('email')}
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${id}-password`}>비밀번호</Label>
        <Input type="password" autoComplete={passwordAutoComplete} {...fieldProps('password')} />
        {fieldError('password')}
      </div>
      <Button type="submit" className="w-full" disabled={pending}>
        {pending ? pendingLabel : submitLabel}
      </Button>
    </form>
  )
}
