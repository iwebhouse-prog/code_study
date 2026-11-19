import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface Props<T extends string> {
  /** Accessible name of the tab list. */
  label: string
  tabs: readonly { id: T; label: string }[]
  value: T
  onValueChange: (value: T) => void
  /** Content of the selected tab. */
  children: ReactNode
}

// Only the selected panel is rendered. Every tab is a button, so Tab and Enter
// work from the keyboard.
export function Tabs<T extends string>({ label, tabs, value, onValueChange, children }: Props<T>) {
  const id = useId()
  return (
    <div className="space-y-4">
      <div role="tablist" aria-label={label} className="flex gap-1 border-b">
        {tabs.map((tab) => {
          const selected = tab.id === value
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`${id}-tab-${tab.id}`}
              aria-selected={selected}
              aria-controls={`${id}-panel`}
              onClick={() => onValueChange(tab.id)}
              className={cn(
                '-mb-px border-b-2 px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                selected
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              {tab.label}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-tab-${value}`}>
        {children}
      </div>
    </div>
  )
}
