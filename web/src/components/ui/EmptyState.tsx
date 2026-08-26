export function EmptyState({
  title,
  description,
}: {
  title: string
  description?: string
}) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-surface px-6 py-12 text-center">
      <p className="text-base font-medium text-text">{title}</p>
      {description ? (
        <p className="mx-auto mt-1 max-w-md text-sm text-muted">{description}</p>
      ) : null}
    </div>
  )
}
