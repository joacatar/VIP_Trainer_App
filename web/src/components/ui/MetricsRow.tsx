export function MetricsRow({
  items,
}: {
  items: Array<{ label: string; value: string | number; hint?: string }>
}) {
  const shown = items.slice(0, 4)
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {shown.map((item) => (
        <div
          key={item.label}
          className="rounded-lg border border-border bg-surface px-4 py-3"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-muted">
            {item.label}
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-text">
            {item.value}
          </p>
          {item.hint ? (
            <p className="mt-0.5 text-xs text-muted">{item.hint}</p>
          ) : null}
        </div>
      ))}
    </div>
  )
}
