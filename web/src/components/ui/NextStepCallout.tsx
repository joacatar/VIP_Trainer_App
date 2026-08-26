import type { ReactNode } from 'react'

export function NextStepCallout({
  title = 'Next step',
  children,
}: {
  title?: string
  children: ReactNode
}) {
  return (
    <aside className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">
        {title}
      </p>
      <div className="mt-1 text-sm text-text">{children}</div>
    </aside>
  )
}
