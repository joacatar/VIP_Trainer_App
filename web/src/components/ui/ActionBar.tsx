import type { ReactNode } from 'react'

export function ActionBar({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
      {children}
    </div>
  )
}
