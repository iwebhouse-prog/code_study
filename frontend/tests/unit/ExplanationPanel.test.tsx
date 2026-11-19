import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ExplanationPanel } from '../../src/components/document/ExplanationPanel'
import { APP_CONTENT } from '../helpers/documents'

const CHAPTER_TITLES = [
  '1. 이 코드가 하는 일',
  '2. 미리 알아둘 개념',
  '3. 코드 구조 한눈에 보기',
  '4. 한 줄씩 살펴보기',
  '5. 실행 흐름 따라가기',
  '6. 핵심 개념 정리',
  '7. 자주 하는 실수',
]

function rect(top: number, bottom: number): DOMRect {
  return { top, bottom, left: 0, right: 0, width: 0, height: bottom - top } as DOMRect
}

const scrollTo = vi.fn()

beforeEach(() => {
  // jsdom has no layout and no Element.scrollTo.
  HTMLElement.prototype.scrollTo = scrollTo as unknown as typeof HTMLElement.prototype.scrollTo
})

afterEach(() => {
  scrollTo.mockReset()
})

function renderPanel(props: Partial<Parameters<typeof ExplanationPanel>[0]> = {}) {
  const onSelectExplanation = vi.fn()
  const view = render(
    <ExplanationPanel
      content={APP_CONTENT}
      activeExplanationIndex={null}
      onSelectExplanation={onSelectExplanation}
      {...props}
    />,
  )
  return { ...view, onSelectExplanation }
}

describe('ExplanationPanel chapter navigation (T101)', () => {
  it('lists all 7 chapters in a labelled navigation', () => {
    renderPanel()
    const nav = screen.getByRole('navigation', { name: '챕터 이동' })
    const buttons = within(nav).getAllByRole('button')
    expect(buttons.map((button) => button.textContent)).toEqual(CHAPTER_TITLES)
  })

  it('renders every chapter heading', () => {
    renderPanel()
    for (const title of CHAPTER_TITLES) {
      expect(screen.getByRole('heading', { level: 3, name: title })).toBeInTheDocument()
    }
  })

  it('highlights the first chapter at the start', () => {
    renderPanel()
    const current = screen
      .getAllByRole('button', { name: /^\d\. / })
      .filter((button) => button.getAttribute('aria-current') === 'true')
    expect(current.map((button) => button.textContent)).toEqual([CHAPTER_TITLES[0]])
  })

  it('marks the clicked chapter as current and scrolls the panel to it', async () => {
    renderPanel()
    const nav = screen.getByRole('navigation', { name: '챕터 이동' })
    const scroller = screen.getByRole('region', { name: '학습 문서 설명' })
    const section = screen.getByRole('heading', { name: CHAPTER_TITLES[4] }).closest('section')!
    vi.spyOn(scroller, 'getBoundingClientRect').mockReturnValue(rect(100, 500))
    vi.spyOn(section, 'getBoundingClientRect').mockReturnValue(rect(700, 900))

    await userEvent.click(within(nav).getByRole('button', { name: CHAPTER_TITLES[4] }))

    expect(within(nav).getByRole('button', { name: CHAPTER_TITLES[4] })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(within(nav).getByRole('button', { name: CHAPTER_TITLES[0] })).not.toHaveAttribute(
      'aria-current',
    )
    expect(scrollTo).toHaveBeenCalledWith({ top: 600 })
  })

  it('can be used from the keyboard', async () => {
    renderPanel()
    const nav = screen.getByRole('navigation', { name: '챕터 이동' })
    within(nav).getByRole('button', { name: CHAPTER_TITLES[2] }).focus()
    await userEvent.keyboard('{Enter}')
    expect(within(nav).getByRole('button', { name: CHAPTER_TITLES[2] })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('makes the scrolling area reachable by keyboard', () => {
    renderPanel()
    expect(screen.getByRole('region', { name: '학습 문서 설명' })).toHaveAttribute('tabindex', '0')
  })
})

describe('ExplanationPanel chapters 3, 5, 6, 7 (shared renderer)', () => {
  it('shows chapter 3 flowchart text and the file roles', () => {
    renderPanel()
    const section = screen.getByRole('heading', { name: CHAPTER_TITLES[2] }).closest('section')!
    expect(section).toHaveTextContent('graph TD; A[시작] --> B[끝];')
    expect(section).toHaveTextContent('even_odd.py')
    expect(section).toHaveTextContent('짝수 홀수를 판별합니다.')
    expect(section).toHaveTextContent('main.py')
  })

  it('shows chapter 5 steps with their data state', () => {
    renderPanel()
    const section = screen.getByRole('heading', { name: CHAPTER_TITLES[4] }).closest('section')!
    expect(section).toHaveTextContent('n이 1일 때 홀수입니다.')
    expect(section).toHaveTextContent('n = 2')
  })

  it('shows chapter 6 concepts', () => {
    renderPanel()
    const section = screen.getByRole('heading', { name: CHAPTER_TITLES[5] }).closest('section')!
    expect(section).toHaveTextContent('Boolean')
    expect(section).toHaveTextContent('참 또는 거짓입니다.')
    expect(section).toHaveTextContent('조건을 판단하려고 씁니다.')
    expect(section).toHaveTextContent('if문에 씁니다.')
  })

  it('shows chapter 7 mistakes', () => {
    renderPanel()
    const section = screen.getByRole('heading', { name: CHAPTER_TITLES[6] }).closest('section')!
    expect(section).toHaveTextContent('range(1, 5)')
    expect(section).toHaveTextContent('range(1, 6)')
    expect(section).toHaveTextContent('5가 빠집니다.')
    expect(section).toHaveTextContent('끝 숫자에 1을 더합니다.')
  })
})

describe('ExplanationPanel chapter 4 link to the code', () => {
  it('reports the clicked explanation', async () => {
    const { onSelectExplanation } = renderPanel()
    await userEvent.click(screen.getByRole('button', { name: /main\.py 1~3줄/ }))
    expect(onSelectExplanation).toHaveBeenCalledWith(2)
  })

  it('makes chapter 4 current and scrolls to the active explanation when the code scrolls to it', () => {
    const { rerender } = renderPanel()
    const scroller = screen.getByRole('region', { name: '학습 문서 설명' })
    const item = document.querySelector('[data-explanation-index="1"]')!
    vi.spyOn(scroller, 'getBoundingClientRect').mockReturnValue(rect(100, 500))
    vi.spyOn(item, 'getBoundingClientRect').mockReturnValue(rect(800, 950))

    rerender(
      <ExplanationPanel
        content={APP_CONTENT}
        activeExplanationIndex={1}
        onSelectExplanation={vi.fn()}
      />,
    )

    expect(scrollTo).toHaveBeenCalledWith({ top: 700 })
    expect(screen.getByRole('button', { name: CHAPTER_TITLES[3] })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('does not scroll when the active explanation is already fully visible', () => {
    const { rerender } = renderPanel()
    const scroller = screen.getByRole('region', { name: '학습 문서 설명' })
    const item = document.querySelector('[data-explanation-index="1"]')!
    vi.spyOn(scroller, 'getBoundingClientRect').mockReturnValue(rect(100, 500))
    vi.spyOn(item, 'getBoundingClientRect').mockReturnValue(rect(150, 300))

    rerender(
      <ExplanationPanel
        content={APP_CONTENT}
        activeExplanationIndex={1}
        onSelectExplanation={vi.fn()}
      />,
    )

    expect(scrollTo).not.toHaveBeenCalled()
  })
})
