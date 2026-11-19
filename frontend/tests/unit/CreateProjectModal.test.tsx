import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import CreateProjectModal from '../../src/components/project/CreateProjectModal'
import { ApiError } from '../../src/services/api-client'

function renderModal(onSubmit = vi.fn().mockResolvedValue(undefined), open = true) {
  const onOpenChange = vi.fn()
  render(<CreateProjectModal open={open} onOpenChange={onOpenChange} onSubmit={onSubmit} />)
  return { onSubmit, onOpenChange }
}

const titleInput = () => screen.getByLabelText('프로젝트 제목')
const submitButton = () => screen.getByRole('button', { name: '만들기' })

describe('CreateProjectModal', () => {
  it('renders nothing while closed', () => {
    renderModal(undefined, false)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('is a named dialog with a title field and an optional description', () => {
    renderModal()
    expect(screen.getByRole('dialog', { name: '새 프로젝트' })).toBeInTheDocument()
    expect(titleInput()).toBeRequired()
    expect(screen.getByLabelText('설명 (선택)')).not.toBeRequired()
  })

  it('submits the trimmed title and description, then closes', async () => {
    const { onSubmit, onOpenChange } = renderModal()
    await userEvent.type(titleInput(), '  My Todo App  ')
    await userEvent.type(screen.getByLabelText('설명 (선택)'), '할 일 앱')
    await userEvent.click(submitButton())
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
    expect(onSubmit).toHaveBeenCalledWith({ title: 'My Todo App', description: '할 일 앱' })
  })

  it('leaves the description out when it is blank', async () => {
    const { onSubmit } = renderModal()
    await userEvent.type(titleInput(), 'A')
    await userEvent.type(screen.getByLabelText('설명 (선택)'), '   ')
    await userEvent.click(submitButton())
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ title: 'A' }))
  })

  it('rejects an empty or blank title without calling the server', async () => {
    const { onSubmit } = renderModal()
    await userEvent.click(submitButton())
    expect(
      await screen.findByText('프로젝트 제목은 최소 1자 이상이어야 합니다.'),
    ).toBeInTheDocument()
    await userEvent.type(titleInput(), '   ')
    await userEvent.click(submitButton())
    expect(screen.getByText('프로젝트 제목은 최소 1자 이상이어야 합니다.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('links the title error to the field', async () => {
    renderModal()
    await userEvent.click(submitButton())
    const message = await screen.findByText('프로젝트 제목은 최소 1자 이상이어야 합니다.')
    expect(titleInput()).toHaveAttribute('aria-invalid', 'true')
    expect(titleInput().getAttribute('aria-describedby')).toBe(message.id)
  })

  it('rejects a title longer than 255 characters', async () => {
    const { onSubmit } = renderModal()
    await userEvent.click(titleInput())
    await userEvent.paste('a'.repeat(256))
    await userEvent.click(submitButton())
    expect(await screen.findByText('프로젝트 제목은 255자를 넘을 수 없습니다.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('accepts a title of exactly 255 characters', async () => {
    const { onSubmit } = renderModal()
    await userEvent.click(titleInput())
    await userEvent.paste('a'.repeat(255))
    await userEvent.click(submitButton())
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
  })

  it('shows the server title error next to the field and stays open', async () => {
    const onSubmit = vi.fn().mockRejectedValue(
      new ApiError({
        status: 400,
        code: 'validation_error',
        message: '입력값을 확인하세요.',
        details: { fields: [{ field: 'title', message: '서버: 제목이 올바르지 않습니다.' }] },
      }),
    )
    const { onOpenChange } = renderModal(onSubmit)
    await userEvent.type(titleInput(), 'x')
    await userEvent.click(submitButton())
    const message = await screen.findByText('서버: 제목이 올바르지 않습니다.')
    expect(titleInput().getAttribute('aria-describedby')).toBe(message.id)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(onOpenChange).not.toHaveBeenCalled()
  })

  it('shows a general server message in an alert', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(
        new ApiError({ status: 500, code: 'internal_error', message: '서버 오류' }),
      )
    renderModal(onSubmit)
    await userEvent.type(titleInput(), 'x')
    await userEvent.click(submitButton())
    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류')
  })

  it('shows a fallback message for an unexpected failure', async () => {
    renderModal(vi.fn().mockRejectedValue(new Error('boom')))
    await userEvent.type(titleInput(), 'x')
    await userEvent.click(submitButton())
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '프로젝트를 만들지 못했습니다. 잠시 후 다시 시도하세요.',
    )
  })

  it('disables the button and shows progress while saving', async () => {
    let finish: () => void = () => undefined
    const onSubmit = vi.fn(() => new Promise<void>((resolve) => (finish = resolve)))
    renderModal(onSubmit)
    await userEvent.type(titleInput(), 'x')
    await userEvent.click(submitButton())
    const saving = await screen.findByRole('button', { name: '만드는 중…' })
    expect(saving).toBeDisabled()
    finish()
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
  })

  it('cancel closes the dialog without saving', async () => {
    const { onSubmit, onOpenChange } = renderModal()
    await userEvent.click(screen.getByRole('button', { name: '취소' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
