import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import DevTest from '../../src/pages/dev/DevTest'
import UiTestPanel from '../../src/pages/dev/UiTestPanel'

const section = (name: string) => within(screen.getByRole('region', { name }))

afterEach(() => {
  vi.restoreAllMocks()
})

describe('UiTestPanel sections', () => {
  it.each(['Tailwind 클래스 테스트', 'shadcn/ui 버튼 테스트', '반응형 디자인 테스트'])(
    'has the "%s" section with a heading',
    (name) => {
      render(<UiTestPanel />)
      expect(section(name).getByRole('heading', { name })).toBeInTheDocument()
    },
  )

  it('is part of the /dev-test page without removing earlier tests', () => {
    render(<DevTest />)
    expect(screen.getByRole('button', { name: 'API 호출' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '사용자 설정' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'outline' })).toBeInTheDocument()
  })
})

describe('Tailwind class test', () => {
  it('applies all four classes to one sample box', () => {
    render(<UiTestPanel />)
    const box = section('Tailwind 클래스 테스트').getByTestId('tailwind-sample')
    expect(box).toHaveClass('bg-blue-500', 'text-white', 'p-4', 'rounded-lg')
  })

  it.each([
    ['bg-blue-500', 'background-color: #3b82f6'],
    ['text-white', 'color: #ffffff'],
    ['p-4', 'padding: 1rem'],
    ['rounded-lg', 'border-radius: 0.5rem'],
  ])('explains what %s does', (className, css) => {
    render(<UiTestPanel />)
    const row = section('Tailwind 클래스 테스트').getByRole('row', {
      name: new RegExp(`^${className} `),
    })
    expect(row).toHaveTextContent(css)
  })
})

describe('shadcn/ui button test', () => {
  it.each(['default', 'outline', 'ghost'])('%s button alerts its variant name', async (variant) => {
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => {})
    render(<UiTestPanel />)
    await userEvent.click(section('shadcn/ui 버튼 테스트').getByRole('button', { name: variant }))
    expect(alert).toHaveBeenCalledExactlyOnceWith(variant)
  })

  it('renders each button with its own variant style', () => {
    render(<UiTestPanel />)
    const buttons = section('shadcn/ui 버튼 테스트')
    expect(buttons.getAllByRole('button')).toHaveLength(3)
    expect(buttons.getByRole('button', { name: 'default' })).toHaveClass('bg-primary')
    expect(buttons.getByRole('button', { name: 'outline' })).toHaveClass('border')
    expect(buttons.getByRole('button', { name: 'ghost' })).not.toHaveClass('bg-primary', 'border')
  })
})

describe('responsive test', () => {
  it('lays out three cards at 1, 2 and 3 columns', () => {
    render(<UiTestPanel />)
    const grid = section('반응형 디자인 테스트').getByTestId('responsive-grid')
    expect(grid).toHaveClass('grid', 'grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-3')
    expect(grid.children).toHaveLength(3)
  })
})
