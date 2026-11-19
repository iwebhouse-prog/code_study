import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import PasteCode from '../../src/components/upload/PasteCode'

function renderPaste(props: Partial<React.ComponentProps<typeof PasteCode>> = {}) {
  const onCodeChange = vi.fn()
  const onLanguageChange = vi.fn()
  render(
    <PasteCode
      code=""
      language=""
      onCodeChange={onCodeChange}
      onLanguageChange={onLanguageChange}
      {...props}
    />,
  )
  return { onCodeChange, onLanguageChange }
}

describe('PasteCode', () => {
  it('has a labelled textarea', () => {
    renderPaste({ code: 'print(1)' })
    expect(screen.getByLabelText('붙여넣을 코드')).toHaveValue('print(1)')
  })

  it('reports typed code', async () => {
    const { onCodeChange } = renderPaste()
    await userEvent.type(screen.getByLabelText('붙여넣을 코드'), 'a')
    expect(onCodeChange).toHaveBeenCalledWith('a')
  })

  it('has a required language select with the Korean labels', () => {
    renderPaste()
    const select = screen.getByLabelText('프로그래밍 언어')
    expect(select).toBeRequired()
    const labels = within(select)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(labels).toEqual([
      '언어 선택',
      'Python',
      'JavaScript',
      'TypeScript',
      'HTML',
      'CSS',
      'Java',
      'C',
      'C++',
      'Markdown',
      '일반 텍스트',
    ])
  })

  it('reports the language value the API expects', async () => {
    const { onLanguageChange } = renderPaste()
    await userEvent.selectOptions(screen.getByLabelText('프로그래밍 언어'), 'C++')
    expect(onLanguageChange).toHaveBeenCalledWith('cpp')
  })

  it('shows the selected language', () => {
    renderPaste({ language: 'text' })
    expect(screen.getByLabelText('프로그래밍 언어')).toHaveValue('text')
  })
})
