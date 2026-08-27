import { Link } from 'react-router-dom'
import { caseCatalogLabel, casePhaseNo } from '@/lib/domain/caseLabels'
import { isOverdue, traineeAttentionState } from '@/lib/domain/ownership'
import type { AttentionState, CaseRow } from '@/lib/types'

/**
 * A visual progress map — a grid of case nodes, colored by status,
 * clickable — instead of only a flat list. Borrowed deliberately from
 * education products (Khan Academy's mastery grid, Canvas's module
 * checklist, Duolingo's path): the thing a flat list can't give a learner
 * is "how far through this am I, at a glance." Only ever renders cases the
 * trainee can already see (never a `not_started` placeholder — gotcha #1).
 */

const TONE: Record<AttentionState, { fill: string; ring: string; label: string }> = {
  approved: { fill: 'bg-success text-white', ring: '', label: 'Approved' },
  needs_trainer: {
    fill: 'bg-surface text-primary',
    ring: 'ring-2 ring-primary',
    label: 'With trainer',
  },
  with_trainee: {
    fill: 'bg-surface text-attention',
    ring: 'ring-2 ring-attention',
    label: 'Needs you',
  },
  assigned: {
    fill: 'bg-surface text-attention',
    ring: 'ring-2 ring-attention',
    label: 'Needs you',
  },
}

export function TrainingJourney({ cases }: { cases: CaseRow[] }) {
  const phase1 = cases
    .filter((c) => casePhaseNo(c) === 1)
    .sort((a, b) => a.set_no - b.set_no || a.case_no - b.case_no)
  const phase2 = cases
    .filter((c) => casePhaseNo(c) === 2)
    .sort((a, b) => a.case_no - b.case_no)

  if (phase1.length === 0 && phase2.length === 0) return null

  return (
    <div className="space-y-4">
      {phase1.length > 0 ? (
        <JourneyRow title="Phase 1" cases={phase1} total={32} />
      ) : null}
      {phase2.length > 0 ? (
        <JourneyRow title="Live cases" cases={phase2} total={30} />
      ) : null}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        {(
          [
            ['approved', 'Approved'],
            ['needs_trainer', 'With trainer'],
            ['with_trainee', 'Needs you'],
          ] as const
        ).map(([state, label]) => (
          <span key={state} className="inline-flex items-center gap-1.5">
            <span
              className={`inline-block h-3 w-3 rounded-full ${TONE[state].fill} ${TONE[state].ring}`}
            />
            {label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full bg-surface ring-2 ring-danger" />
          Overdue
        </span>
      </div>
    </div>
  )
}

function JourneyRow({
  title,
  cases,
  total,
}: {
  title: string
  cases: CaseRow[]
  total: number
}) {
  const approved = cases.filter((c) => c.status === 'approved').length
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-text">{title}</h3>
        <span className="text-xs tabular-nums text-muted">
          {approved}/{total} approved
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {cases.map((c) => {
          const state = traineeAttentionState(c.status)
          const tone = TONE[state]
          const overdue = isOverdue(c.status, c.due_date)
          return (
            <Link
              key={c.id}
              to={`/trainee/cases/${c.id}`}
              title={`${caseCatalogLabel(c)} — ${tone.label}${overdue ? ' — Overdue' : ''}`}
              className={`fade-in flex h-9 w-9 items-center justify-center rounded-full text-xs font-semibold transition-transform hover:scale-110 ${tone.fill} ${
                overdue ? 'ring-2 ring-danger' : tone.ring
              }`}
            >
              {caseCatalogLabel(c).replace(/^L0?/, '')}
            </Link>
          )
        })}
      </div>
    </div>
  )
}
