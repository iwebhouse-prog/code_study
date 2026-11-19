import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import ProjectCard from '../../src/components/project/ProjectCard'
import { APP_PROJECT } from '../helpers/projects'

function renderCard(project = APP_PROJECT) {
  render(
    <MemoryRouter>
      <ProjectCard project={project} />
    </MemoryRouter>,
  )
}

describe('ProjectCard', () => {
  it('shows the title as a link to the project page', () => {
    renderCard()
    expect(screen.getByRole('link', { name: 'My Todo App' })).toHaveAttribute(
      'href',
      `/projects/${APP_PROJECT.id}`,
    )
  })

  it('shows the description', () => {
    renderCard()
    expect(screen.getByText('할 일 앱 만들기')).toBeInTheDocument()
  })

  it('leaves out the description when there is none', () => {
    renderCard({ ...APP_PROJECT, description: null })
    expect(screen.queryByText('할 일 앱 만들기')).not.toBeInTheDocument()
  })

  it('shows completed and total task counts', () => {
    renderCard()
    expect(screen.getByText('완료 2/5 태스크')).toBeInTheDocument()
  })

  it('shows zero counts for a project without tasks', () => {
    renderCard({ ...APP_PROJECT, taskCount: 0, completedTaskCount: 0 })
    expect(screen.getByText('완료 0/0 태스크')).toBeInTheDocument()
  })

  it('shows the last activity date in Korean', () => {
    renderCard({ ...APP_PROJECT, lastActivityAt: '2026-11-10T03:00:00+00:00' })
    expect(screen.getByText('마지막 활동: 2026년 11월 10일')).toBeInTheDocument()
  })
})
