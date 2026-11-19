import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import LoginForm from '../../src/components/auth/LoginForm'
import RegisterForm from '../../src/components/auth/RegisterForm'
import { ApiError } from '../../src/services/api-client'

const email = () => screen.getByLabelText('이메일')
const password = () => screen.getByLabelText('비밀번호')

async function fill(emailValue: string, passwordValue: string) {
  if (emailValue) await userEvent.type(email(), emailValue)
  if (passwordValue) await userEvent.type(password(), passwordValue)
}

const validationError = new ApiError({
  status: 400,
  code: 'validation_error',
  message: '입력값을 확인하세요.',
  details: { fields: [{ field: 'password', message: '서버: 비밀번호가 약합니다.' }] },
})

describe.each([
  ['LoginForm', LoginForm, '로그인'],
  ['RegisterForm', RegisterForm, '회원가입'],
] as const)('%s (shared behaviour)', (_name, Form, buttonName) => {
  it('has labelled email and password inputs and a submit button', () => {
    render(<Form onSubmit={vi.fn()} />)
    expect(email()).toHaveAttribute('type', 'email')
    expect(password()).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: buttonName })).toHaveAttribute('type', 'submit')
  })

  it('submits the trimmed email and the password as typed', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<Form onSubmit={onSubmit} />)
    await fill('  a@b.com ', 'abcd1234')
    await userEvent.click(screen.getByRole('button', { name: buttonName }))
    expect(onSubmit).toHaveBeenCalledWith({ email: 'a@b.com', password: 'abcd1234' })
  })

  it('asks for an email and does not submit without one', async () => {
    const onSubmit = vi.fn()
    render(<Form onSubmit={onSubmit} />)
    await fill('', 'abcd1234')
    await userEvent.click(screen.getByRole('button', { name: buttonName }))
    expect(screen.getByText('이메일을 입력하세요.')).toBeInTheDocument()
    expect(email()).toHaveAttribute('aria-invalid', 'true')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('rejects an email without a domain', async () => {
    const onSubmit = vi.fn()
    render(<Form onSubmit={onSubmit} />)
    await fill('not-an-email', 'abcd1234')
    await userEvent.click(screen.getByRole('button', { name: buttonName }))
    expect(screen.getByText('올바른 이메일 주소를 입력하세요.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('shows a loading state and blocks double submits while waiting', async () => {
    let finish: () => void = () => undefined
    const onSubmit = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve
        }),
    )
    render(<Form onSubmit={onSubmit} />)
    await fill('a@b.com', 'abcd1234')
    await userEvent.click(screen.getByRole('button', { name: buttonName }))
    const busy = screen.getByRole('button', { name: /중/ })
    expect(busy).toBeDisabled()
    await userEvent.click(busy)
    fireEvent.submit(busy.closest('form')!)
    expect(onSubmit).toHaveBeenCalledTimes(1)
    finish()
    expect(await screen.findByRole('button', { name: buttonName })).toBeEnabled()
  })

  it('shows server field errors next to the field and the message in an alert', async () => {
    const onSubmit = vi.fn().mockRejectedValue(validationError)
    render(<Form onSubmit={onSubmit} />)
    await fill('a@b.com', 'abcd1234')
    await userEvent.click(screen.getByRole('button', { name: buttonName }))
    expect(await screen.findByRole('alert')).toHaveTextContent('입력값을 확인하세요.')
    const fieldMessage = screen.getByText('서버: 비밀번호가 약합니다.')
    expect(password()).toHaveAttribute('aria-invalid', 'true')
    expect(password().getAttribute('aria-describedby')).toBe(fieldMessage.id)
  })

  it('shows the message of other API errors in an alert', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(new ApiError({ status: 401, code: 'x', message: '서버가 말한 문장' }))
    render(<Form onSubmit={onSubmit} />)
    await fill('a@b.com', 'abcd1234')
    await userEvent.click(screen.getByRole('button', { name: buttonName }))
    expect(await screen.findByRole('alert')).toHaveTextContent('서버가 말한 문장')
  })

  it('shows a generic Korean message for unexpected errors', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error('boom'))
    render(<Form onSubmit={onSubmit} />)
    await fill('a@b.com', 'abcd1234')
    await userEvent.click(screen.getByRole('button', { name: buttonName }))
    expect(await screen.findByRole('alert')).toHaveTextContent('문제가 발생했습니다')
  })

  it('clears the previous server error when submitting again', async () => {
    const onSubmit = vi.fn().mockRejectedValueOnce(validationError).mockResolvedValueOnce(undefined)
    render(<Form onSubmit={onSubmit} />)
    await fill('a@b.com', 'abcd1234')
    await userEvent.click(screen.getByRole('button', { name: buttonName }))
    await screen.findByRole('alert')
    await userEvent.click(screen.getByRole('button', { name: buttonName }))
    await screen.findByRole('button', { name: buttonName })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText('서버: 비밀번호가 약합니다.')).not.toBeInTheDocument()
  })
})

describe('LoginForm', () => {
  it('only asks that a password is present (the server judges it)', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<LoginForm onSubmit={onSubmit} />)
    await fill('a@b.com', 'x')
    await userEvent.click(screen.getByRole('button', { name: '로그인' }))
    expect(onSubmit).toHaveBeenCalledWith({ email: 'a@b.com', password: 'x' })
  })

  it('asks for a password when it is empty', async () => {
    const onSubmit = vi.fn()
    render(<LoginForm onSubmit={onSubmit} />)
    await fill('a@b.com', '')
    await userEvent.click(screen.getByRole('button', { name: '로그인' }))
    expect(screen.getByText('비밀번호를 입력하세요.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('RegisterForm password rules', () => {
  async function submitWith(passwordValue: string) {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<RegisterForm onSubmit={onSubmit} />)
    await fill('a@b.com', passwordValue)
    await userEvent.click(screen.getByRole('button', { name: '회원가입' }))
    return onSubmit
  }

  it('requires at least 8 characters', async () => {
    const onSubmit = await submitWith('abc123')
    expect(screen.getByText('비밀번호는 8자 이상이어야 합니다.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('requires letters', async () => {
    const onSubmit = await submitWith('12345678')
    expect(screen.getByText('비밀번호는 영문자와 숫자를 모두 포함해야 합니다.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('requires digits', async () => {
    const onSubmit = await submitWith('abcdefgh')
    expect(screen.getByText('비밀번호는 영문자와 숫자를 모두 포함해야 합니다.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('allows at most 72 bytes', async () => {
    const onSubmit = await submitWith('a1'.repeat(37))
    expect(
      screen.getByText('비밀번호가 너무 깁니다. 72바이트 이하로 입력하세요.'),
    ).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('counts bytes, not characters (Korean letters take 3 bytes)', async () => {
    const onSubmit = await submitWith('가'.repeat(24) + 'a1')
    expect(
      screen.getByText('비밀번호가 너무 깁니다. 72바이트 이하로 입력하세요.'),
    ).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('accepts a password with letters and digits', async () => {
    const onSubmit = await submitWith('abcd1234')
    expect(onSubmit).toHaveBeenCalledWith({ email: 'a@b.com', password: 'abcd1234' })
  })

  it('shows an email_taken answer in an alert', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(
        new ApiError({ status: 409, code: 'email_taken', message: '이미 가입된 이메일입니다.' }),
      )
    render(<RegisterForm onSubmit={onSubmit} />)
    await fill('a@b.com', 'abcd1234')
    await userEvent.click(screen.getByRole('button', { name: '회원가입' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 가입된 이메일입니다.')
  })
})
