import { caseTitle } from '@/lib/domain/caseLabels'
import {
  caseOwner,
  formatDue,
  isOverdue,
  nextStep,
  ownerLabel,
} from '@/lib/domain/ownership'
import type { AppRole, CaseRow } from '@/lib/types'
import { StatusBadge } from './StatusBadge'

export function CaseHeader({
  caseRow,
  role,
  traineeName,
}: {
  caseRow: CaseRow
  role: AppRole
  traineeName?: string
}) {
  const owner = caseOwner(caseRow.status)
  const overdue = isOverdue(caseRow.status, caseRow.due_date)
  const step = nextStep(caseRow.status, role)
  const instruction = (caseRow.instruction ?? '').trim()

  return (
    <section className="rounded-lg border border-border bg-surface p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold text-text">
            {caseTitle(caseRow)}
          </h2>
          {traineeName ? (
            <p className="mt-0.5 text-sm text-muted">{traineeName}</p>
          ) : null}
        </div>
        <StatusBadge status={caseRow.status} />
      </div>

      <dl className="mt-4 grid gap-3 sm:grid-cols-3">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-muted">
            Due
          </dt>
          <dd
            className={`mt-0.5 text-sm font-medium ${overdue ? 'text-danger' : 'text-text'}`}
          >
            {formatDue(caseRow.due_date)}
            {overdue ? ' · Overdue' : ''}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-muted">
            Next owner
          </dt>
          <dd className="mt-0.5 text-sm font-medium text-text">
            {ownerLabel(owner)}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-muted">
            Next action
          </dt>
          <dd className="mt-0.5 text-sm font-medium text-text">{step}</dd>
        </div>
      </dl>

      {instruction ? (
        <div className="mt-4 rounded-md border border-attention/40 bg-attention/10 px-3 py-2 text-sm text-text">
          <p className="font-medium text-attention">Instruction</p>
          <p className="mt-1 whitespace-pre-wrap">{instruction}</p>
        </div>
      ) : null}
    </section>
  )
}
