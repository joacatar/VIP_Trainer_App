import type { CaseStatus } from '@/lib/types'
import { STATUS_LABELS } from '@/lib/domain/ownership'

const TONE: Record<string, string> = {
  not_started: 'bg-surface-2 text-muted border-border',
  assigned: 'bg-blue-50 text-primary border-primary/30 dark:bg-primary/15',
  submitted: 'bg-amber-50 text-attention border-attention/30 dark:bg-attention/15',
  awaiting_resubmission:
    'bg-amber-50 text-attention border-attention/30 dark:bg-attention/15',
  in_review: 'bg-violet-50 text-violet-800 border-violet-200 dark:bg-violet-500/15 dark:text-violet-200',
  corrections_sent:
    'bg-orange-50 text-orange-800 border-orange-200 dark:bg-orange-500/15 dark:text-orange-200',
  approved: 'bg-emerald-50 text-success border-success/30 dark:bg-success/15',
  blocked: 'bg-red-50 text-danger border-danger/30 dark:bg-danger/15',
}

export function StatusBadge({ status }: { status: CaseStatus | string }) {
  const label = STATUS_LABELS[status as CaseStatus] ?? status
  const tone = TONE[status] ?? TONE.not_started
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${tone}`}
    >
      {label}
    </span>
  )
}
