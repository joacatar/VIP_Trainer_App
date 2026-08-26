/** Small SVG progress ring — "approved / total" reads as a shape, not just
 * a fraction, the way a Canvas-style course-progress indicator would. */
export function ProgressRing({
  value,
  total,
  size = 36,
  stroke = 4,
}: {
  value: number
  total: number
  size?: number
  stroke?: number
}) {
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const pct = total > 0 ? Math.min(1, value / total) : 0
  const offset = circumference * (1 - pct)

  return (
    <div className="inline-flex items-center gap-2">
      <svg width={size} height={size} className="shrink-0 -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--surface-2)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={pct >= 1 ? 'var(--success)' : 'var(--primary)'}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 300ms ease' }}
        />
      </svg>
      <span className="text-sm tabular-nums text-text">
        {value}/{total}
      </span>
    </div>
  )
}
