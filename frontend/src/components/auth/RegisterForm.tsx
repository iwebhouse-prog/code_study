import CredentialsForm, { type CredentialsFormProps } from './CredentialsForm'

const MIN_PASSWORD_LENGTH = 8
// bcrypt ignores everything after 72 bytes, so the backend rejects longer ones.
const MAX_PASSWORD_BYTES = 72

// Same rules as the backend UserService; the server's answer stays final.
function checkPassword(password: string): string | undefined {
  if (password.length < MIN_PASSWORD_LENGTH) return '비밀번호는 8자 이상이어야 합니다.'
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
    return '비밀번호는 영문자와 숫자를 모두 포함해야 합니다.'
  }
  if (new TextEncoder().encode(password).length > MAX_PASSWORD_BYTES) {
    return '비밀번호가 너무 깁니다. 72바이트 이하로 입력하세요.'
  }
  return undefined
}

export default function RegisterForm({ onSubmit }: CredentialsFormProps) {
  return (
    <CredentialsForm
      onSubmit={onSubmit}
      submitLabel="회원가입"
      pendingLabel="가입 중…"
      passwordAutoComplete="new-password"
      checkPassword={checkPassword}
    />
  )
}
