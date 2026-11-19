import { useToastStore } from '@/stores/toast-store'

// The live region exists from the start: screen readers only announce changes
// to a region that was already on the page.
export default function Toaster() {
  const toasts = useToastStore((state) => state.toasts)
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed right-4 top-4 z-50 flex flex-col gap-2"
    >
      {toasts.map((toast) => (
        <p
          key={toast.id}
          className="rounded-md border bg-card px-4 py-3 text-sm text-card-foreground shadow-lg"
        >
          {toast.message}
        </p>
      ))}
    </div>
  )
}
