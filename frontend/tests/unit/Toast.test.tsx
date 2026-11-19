import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Toaster from '../../src/components/ui/toast'
import { TOAST_DURATION_MS, useToastStore } from '../../src/stores/toast-store'

beforeEach(() => {
  vi.useFakeTimers()
  useToastStore.setState({ toasts: [] })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('Toaster', () => {
  it('has a live region that is empty at first', () => {
    render(<Toaster />)
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
  })

  it('announces a toast message in the live region', () => {
    render(<Toaster />)
    act(() => useToastStore.getState().show('프로젝트가 생성되었습니다.'))
    expect(screen.getByRole('status')).toHaveTextContent('프로젝트가 생성되었습니다.')
  })

  it('sits in the top-right corner', () => {
    render(<Toaster />)
    expect(screen.getByRole('status').className).toMatch(/top-4/)
    expect(screen.getByRole('status').className).toMatch(/right-4/)
  })

  it('disappears after 3 seconds', () => {
    expect(TOAST_DURATION_MS).toBe(3000)
    render(<Toaster />)
    act(() => useToastStore.getState().show('안녕'))
    act(() => vi.advanceTimersByTime(2999))
    expect(screen.getByRole('status')).toHaveTextContent('안녕')
    act(() => vi.advanceTimersByTime(1))
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
  })

  it('shows several toasts and removes each one on its own time', () => {
    render(<Toaster />)
    act(() => useToastStore.getState().show('첫째'))
    act(() => vi.advanceTimersByTime(1000))
    act(() => useToastStore.getState().show('둘째'))
    expect(screen.getByRole('status')).toHaveTextContent('첫째')
    expect(screen.getByRole('status')).toHaveTextContent('둘째')
    act(() => vi.advanceTimersByTime(2000))
    expect(screen.getByRole('status')).not.toHaveTextContent('첫째')
    expect(screen.getByRole('status')).toHaveTextContent('둘째')
  })
})
