import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Link } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

describe('cn', () => {
  it('joins class names and skips empty values', () => {
    expect(cn('a', false, undefined, 'b')).toBe('a b')
  })

  it('lets later Tailwind classes override earlier ones', () => {
    expect(cn('px-2 text-sm', 'px-4')).toBe('text-sm px-4')
  })
})

describe('Button', () => {
  it('fires onClick', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>저장</Button>)
    await userEvent.click(screen.getByRole('button', { name: '저장' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('uses the primary style by default and accepts variants', () => {
    render(
      <>
        <Button>기본</Button>
        <Button variant="destructive">삭제</Button>
        <Button variant="outline" size="sm">
          취소
        </Button>
      </>,
    )
    expect(screen.getByRole('button', { name: '기본' })).toHaveClass('bg-primary')
    expect(screen.getByRole('button', { name: '삭제' })).toHaveClass('bg-destructive')
    const outline = screen.getByRole('button', { name: '취소' })
    expect(outline).toHaveClass('border', 'h-9')
  })

  it('does not submit a form unless asked', () => {
    render(<Button>보통</Button>)
    expect(screen.getByRole('button', { name: '보통' })).not.toHaveAttribute('type', 'submit')
  })

  it('disabled button ignores clicks', async () => {
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        잠김
      </Button>,
    )
    await userEvent.click(screen.getByRole('button', { name: '잠김' }))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('asChild styles a router link as a button', () => {
    render(
      <MemoryRouter>
        <Button asChild>
          <Link to="/">이동</Link>
        </Button>
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: '이동' })
    expect(link).toHaveClass('bg-primary')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})

describe('form controls', () => {
  it('Label is connected to its Input', async () => {
    render(
      <>
        <Label htmlFor="email">이메일</Label>
        <Input id="email" type="email" />
      </>,
    )
    const input = screen.getByLabelText('이메일')
    await userEvent.type(input, 'a@b.c')
    expect(input).toHaveValue('a@b.c')
  })
})

describe('Card', () => {
  it('renders its parts', () => {
    render(
      <Card data-testid="card" className="max-w-md">
        <CardHeader>
          <CardTitle>제목</CardTitle>
          <CardDescription>설명</CardDescription>
        </CardHeader>
        <CardContent>본문</CardContent>
        <CardFooter>바닥글</CardFooter>
      </Card>,
    )
    expect(screen.getByTestId('card')).toHaveClass('max-w-md', 'rounded-xl')
    for (const text of ['제목', '설명', '본문', '바닥글']) {
      expect(screen.getByText(text)).toBeInTheDocument()
    }
  })
})

describe('Alert', () => {
  it('is announced as an alert and supports the destructive style', () => {
    render(
      <Alert variant="destructive">
        <AlertTitle>저장 실패</AlertTitle>
        <AlertDescription>잠시 후 다시 시도하세요.</AlertDescription>
      </Alert>,
    )
    expect(screen.getByRole('alert')).toHaveClass('text-destructive')
    expect(screen.getByText('저장 실패')).toBeInTheDocument()
  })
})
