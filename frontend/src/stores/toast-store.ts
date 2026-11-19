import { create } from 'zustand'

export const TOAST_DURATION_MS = 3000

interface Toast {
  id: number
  message: string
}

interface ToastState {
  toasts: Toast[]
  /** Shows a message; it removes itself after TOAST_DURATION_MS. */
  show: (message: string) => void
}

let nextId = 0

// A store (not component state) so a toast started on one page is still shown
// after navigating to the next one (create project -> project page).
export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  show: (message) => {
    const id = nextId++
    set((state) => ({ toasts: [...state.toasts, { id, message }] }))
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) }))
    }, TOAST_DURATION_MS)
  },
}))
