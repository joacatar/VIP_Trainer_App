/** A shimmering placeholder, used instead of plain "Loading…" text so the
 * eye reads "something is arriving" rather than "the page stalled". */
export function Skeleton({
  className = 'h-4 w-full',
}: {
  className?: string
}) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />
}

export function SkeletonRows({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-lg border border-border bg-surface px-4 py-3"
        >
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="mt-2 h-3 w-1/3" />
        </div>
      ))}
    </div>
  )
}
