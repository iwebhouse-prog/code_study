import CredentialsForm, { type CredentialsFormProps } from './CredentialsForm'

// Login only checks that a password was typed: the rules apply at sign-up,
// and the server decides whether the credentials are right.
function checkPassword(password: string): string | undefined {
  return password ? undefined : '비밀번호를 입력하세요.'
}

export default function LoginForm({ onSubmit }: CredentialsFormProps) {
  return (
    <CredentialsForm
      onSubmit={onSubmit}
      submitLabel="로그인"
      pendingLabel="로그인 중…"
      passwordAutoComplete="current-password"
      checkPassword={checkPassword}
    />
  )
}
