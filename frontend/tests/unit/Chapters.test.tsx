import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Chapter1 } from '../../src/components/document/chapters/Chapter1'
import { Chapter2 } from '../../src/components/document/chapters/Chapter2'
import { Chapter4 } from '../../src/components/document/chapters/Chapter4'
import { APP_CONTENT } from '../helpers/documents'

describe('Chapter1 (T102)', () => {
  it('shows the numbered title and the summary', () => {
    render(<Chapter1 chapter={APP_CONTENT.chapter1} />)
    expect(
      screen.getByRole('heading', { level: 3, name: '1. 이 코드가 하는 일' }),
    ).toBeInTheDocument()
    expect(screen.getByText('숫자가 짝수인지 홀수인지 알려 줍니다.')).toBeInTheDocument()
  })
})

describe('Chapter2 (T103)', () => {
  it('shows the numbered title and one card per concept', () => {
    render(<Chapter2 chapter={APP_CONTENT.chapter2} />)
    expect(
      screen.getByRole('heading', { level: 3, name: '2. 미리 알아둘 개념' }),
    ).toBeInTheDocument()
    const cards = screen.getAllByRole('listitem')
    expect(cards).toHaveLength(2)
    expect(within(cards[0]).getByRole('heading', { level: 4, name: '함수(def)' })).toBeVisible()
  })

  it('shows explanation, analogy, example and use cases on each card', () => {
    render(<Chapter2 chapter={APP_CONTENT.chapter2} />)
    const [card] = screen.getAllByRole('listitem')
    expect(card).toHaveTextContent('자주 쓰는 기능에 이름을 붙인 상자입니다.')
    expect(card).toHaveTextContent('믹서기 같은 도구입니다.')
    expect(card).toHaveTextContent("def hello(): print('안녕!')")
    expect(card).toHaveTextContent('반복되는 일을 줄일 때 씁니다.')
    for (const label of ['쉬운 설명', '비유', '예시', '자주 쓰이는 곳']) {
      expect(within(card).getByText(label)).toBeInTheDocument()
    }
  })
})

describe('Chapter4 (T104)', () => {
  function renderChapter(activeIndex: number | null = null, onSelect = vi.fn()) {
    render(
      <Chapter4
        chapter={APP_CONTENT.chapter4}
        activeIndex={activeIndex}
        onSelectExplanation={onSelect}
      />,
    )
    return onSelect
  }

  it('shows the numbered title and one item per explanation', () => {
    renderChapter()
    expect(
      screen.getByRole('heading', { level: 3, name: '4. 한 줄씩 살펴보기' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })

  it('shows every field of an explanation', () => {
    renderChapter()
    const [item] = screen.getAllByRole('listitem')
    expect(item).toHaveTextContent('def is_even(number):')
    expect(item).toHaveTextContent('짝수인지 판단하는 함수를 만듭니다.')
    expect(item).toHaveTextContent('def는 함수를 만든다는 뜻입니다.')
    expect(item).toHaveTextContent('2로 나눠 보는 판독기입니다.')
    expect(item).toHaveTextContent('def check(n): return n % 2 != 1')
    expect(item).toHaveTextContent('콜론(:)을 잊지 마세요.')
  })

  it('leaves out empty notes', () => {
    renderChapter()
    const second = screen.getAllByRole('listitem')[1]
    expect(within(second).queryByText('주의할 점')).not.toBeInTheDocument()
  })

  it('names each item by file and line range (single line without a range)', () => {
    renderChapter()
    expect(screen.getByRole('button', { name: /even_odd\.py 1~2줄/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /even_odd\.py 4줄/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /main\.py 1~3줄/ })).toBeInTheDocument()
  })

  it('reports the index of the clicked item', async () => {
    const onSelect = renderChapter()
    await userEvent.click(screen.getByRole('button', { name: /main\.py 1~3줄/ }))
    expect(onSelect).toHaveBeenCalledWith(2)
  })

  it('can be used from the keyboard', async () => {
    const onSelect = renderChapter()
    screen.getByRole('button', { name: /even_odd\.py 4줄/ }).focus()
    await userEvent.keyboard('{Enter}')
    expect(onSelect).toHaveBeenCalledWith(1)
  })

  it('marks the active item as pressed', () => {
    renderChapter(1)
    const buttons = screen.getAllByRole('button')
    expect(buttons.map((b) => b.getAttribute('aria-pressed'))).toEqual(['false', 'true', 'false'])
  })

  it('tags each item with its index so the panel can scroll to it', () => {
    renderChapter()
    const items = screen.getAllByRole('listitem')
    expect(items.map((item) => item.getAttribute('data-explanation-index'))).toEqual([
      '0',
      '1',
      '2',
    ])
  })
})
