import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import TaskCard from '../../src/components/task/TaskCard'
import type { Task } from '../../src/services/task-service'
import { APP_TASK } from '../helpers/tasks'

function renderCard(task: Task = APP_TASK) {
  render(
    <MemoryRouter>
      <TaskCard task={task} />
    </MemoryRouter>,
  )
}

describe('TaskCard', () => {
  it('shows the task number, title and created date', () => {
    renderCard()
    expect(screen.getByText('Task 1')).toBeInTheDocument()
    expect(screen.getByText('할 일 추가 기능')).toBeInTheDocument()
    expect(screen.getByText('만든 날짜: 2026년 11월 16일')).toBeInTheDocument()
  })

  it('links the title to the task page', () => {
    renderCard()
    expect(screen.getByRole('link', { name: '할 일 추가 기능' })).toHaveAttribute(
      'href',
      `/tasks/${APP_TASK.id}`,
    )
  })

  it('shows the language with its display name', () => {
    renderCard()
    expect(screen.getByText('JavaScript')).toBeInTheDocument()
  })

  it('shows 분석 중 when the language is not known yet', () => {
    renderCard({ ...APP_TASK, code: { ...APP_TASK.code, detectedLanguage: null } })
    expect(screen.getByText('분석 중')).toBeInTheDocument()
  })

  it('shows 분석 중 when there is no code summary', () => {
    renderCard({ ...APP_TASK, code: null })
    expect(screen.getByText('분석 중')).toBeInTheDocument()
  })
})
