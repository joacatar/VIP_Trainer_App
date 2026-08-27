import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { EmptyState } from '@/components/ui/EmptyState'
import { MetricsRow } from '@/components/ui/MetricsRow'
import { NextStepCallout } from '@/components/ui/NextStepCallout'
import { PageHeader } from '@/components/ui/PageHeader'
import { SkeletonRows } from '@/components/ui/Skeleton'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { TrainingJourney } from '@/components/ui/TrainingJourney'
import { useAuth } from '@/hooks/useAuth'
import {
  countOpenCorrectionsByCase,
  getTraineeForUser,
  listCases,
} from '@/lib/api'
import { caseLabel, casePhaseNo } from '@/lib/domain/caseLabels'
import {
  formatDue,
  isOverdue,
  isTraineeActionable,
  shortTraineeStep,
  sortTraineeActionable,
  traineeCtaTitle,
} from '@/lib/domain/ownership'
import type { CaseRow } from '@/lib/types'

type CaseWithOpens = CaseRow & { openCorrections: number }

/**
 * Trainee home — one primary CTA, a short coming-up list, then progress.
 * Actionable queue includes awaiting_resubmission and legacy corrections_sent
 * with open threads (read feedback), sorted by urgency.
 */
export function TraineeDashboardPage() {
  const { user } = useAuth()
  const [phase, setPhase] = useState<1 | 2 | 'all'>('all')
  const [showJourney, setShowJourney] = useState(false)

  const traineeQ = useQuery({
    queryKey: ['trainee-for-user', user?.id],
    queryFn: () => getTraineeForUser(user!.id),
    enabled: !!user,
  })

  const casesQ = useQuery({
    queryKey: ['trainee-cases', traineeQ.data?.id],
    queryFn: () =>
      listCases(traineeQ.data!.id, {
        includeFiles: true,
      }),
    enabled: !!traineeQ.data?.id,
  })

  const visibleCases = useMemo(() => {
    const rows = (casesQ.data ?? []).filter((c) => c.status !== 'not_started')
    if (phase === 'all') return rows
    return rows.filter((c) => casePhaseNo(c) === phase)
  }, [casesQ.data, phase])

  const caseIds = useMemo(() => visibleCases.map((c) => c.id), [visibleCases])

  const opensQ = useQuery({
    queryKey: ['open-correction-counts', traineeQ.data?.id, caseIds.join(',')],
    queryFn: () => countOpenCorrectionsByCase(caseIds),
    enabled: caseIds.length > 0,
  })

  const withOpens: CaseWithOpens[] = useMemo(() => {
    const counts = opensQ.data ?? {}
    return visibleCases.map((c) => ({
      ...c,
      openCorrections: counts[c.id] ?? 0,
    }))
  }, [visibleCases, opensQ.data])

  const actionable = useMemo(() => {
    return sortTraineeActionable(
      withOpens.filter((c) => isTraineeActionable(c.status, c.openCorrections)),
    )
  }, [withOpens])

  const nextUp = actionable[0] ?? null
  const comingUp = actionable.slice(1, 4)

  const waitingOnTrainer = useMemo(
    () =>
      withOpens.filter(
        (c) => c.status === 'in_review' || c.status === 'corrections_sent',
      ).filter((c) => !isTraineeActionable(c.status, c.openCorrections)),
    [withOpens],
  )

  const fixCount = actionable.filter(
    (c) =>
      c.status === 'awaiting_resubmission' ||
      (c.status === 'corrections_sent' && c.openCorrections > 0),
  ).length
  const prepareCount = actionable.filter(
    (c) => c.status === 'assigned' || c.status === 'submitted',
  ).length
  const overdueCount = actionable.filter((c) =>
    isOverdue(c.status, c.due_date),
  ).length
  const approvedCount = withOpens.filter((c) => c.status === 'approved').length

  const hasPhase2 = !!traineeQ.data?.phase_2_started_on

  if (traineeQ.isLoading || casesQ.isLoading) {
    return <SkeletonRows count={4} />
  }

  if (!traineeQ.data) {
    return (
      <EmptyState
        title="No trainee record linked"
        description="Ask your trainer to link your account email to a trainee row."
      />
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="My work"
        description={`Hello ${traineeQ.data.full_name}. One next action, then what’s coming up.`}
      />

      <MetricsRow
        items={[
          { label: 'Fix corrections', value: fixCount },
          { label: 'Prepare / submit', value: prepareCount },
          { label: 'With trainer', value: waitingOnTrainer.length },
          { label: 'Approved', value: approvedCount },
        ]}
      />

      {hasPhase2 ? (
        <div className="inline-flex rounded-md border border-border bg-surface p-1">
          {(
            [
              ['all', 'All'],
              [1, 'Phase 1'],
              [2, 'Live cases'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={label}
              type="button"
              onClick={() => setPhase(value)}
              className={`rounded px-3 py-1.5 text-sm transition-colors duration-150 ${
                phase === value
                  ? 'bg-primary text-primary-fg'
                  : 'text-muted hover:text-text'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      ) : null}

      {nextUp ? (
        <Link
          to={`/trainee/cases/${nextUp.id}`}
          className="block rounded-xl border border-primary/40 bg-primary/5 p-5 transition hover:border-primary"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">
            Up next
            {overdueCount > 0 && isOverdue(nextUp.status, nextUp.due_date)
              ? ' · Overdue'
              : ''}
          </p>
          <p className="mt-1 text-xl font-semibold text-text">
            {traineeCtaTitle(nextUp.status, nextUp.openCorrections)}
          </p>
          <p className="mt-1 text-sm text-muted">
            {caseLabel(nextUp)} · due {formatDue(nextUp.due_date)}
            {nextUp.openCorrections > 0
              ? ` · ${nextUp.openCorrections} open correction${nextUp.openCorrections === 1 ? '' : 's'}`
              : ''}
          </p>
          <p className="mt-3 text-sm font-medium text-primary">Open case →</p>
        </Link>
      ) : (
        <NextStepCallout title="All caught up">
          {waitingOnTrainer.length > 0
            ? `${waitingOnTrainer.length} case${waitingOnTrainer.length === 1 ? '' : 's'} with your trainer. Nothing needs you right now.`
            : 'Nothing waiting on you. Cases appear here once your trainer assigns them.'}
        </NextStepCallout>
      )}

      {comingUp.length > 0 ? (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-muted">Coming up</h2>
          <ul className="space-y-2">
            {comingUp.map((c) => (
              <CaseListRow key={c.id} caseRow={c} />
            ))}
          </ul>
          {actionable.length > 4 ? (
            <p className="mt-2 text-xs text-muted">
              +{actionable.length - 4} more needing you — open any case from
              progress below.
            </p>
          ) : null}
        </section>
      ) : null}

      {waitingOnTrainer.length > 0 ? (
        <details className="rounded-lg border border-border bg-surface">
          <summary className="cursor-pointer select-none px-4 py-3 text-sm font-medium">
            Waiting on trainer ({waitingOnTrainer.length})
          </summary>
          <ul className="space-y-2 border-t border-border p-3">
            {waitingOnTrainer.slice(0, 8).map((c) => (
              <CaseListRow key={c.id} caseRow={c} muted />
            ))}
          </ul>
        </details>
      ) : null}

      {withOpens.length > 0 ? (
        <section>
          <button
            type="button"
            onClick={() => setShowJourney((v) => !v)}
            className="mb-2 text-sm font-semibold text-primary hover:underline"
          >
            {showJourney ? 'Hide progress map' : 'Show progress map'}
          </button>
          {showJourney ? <TrainingJourney cases={withOpens} /> : null}
        </section>
      ) : null}

      <p className="text-sm text-muted">
        <Link to="/trainee/corrections" className="text-primary hover:underline">
          My corrections history
        </Link>
        {' · '}
        See patterns across every case.
      </p>
    </div>
  )
}

function CaseListRow({
  caseRow,
  muted,
}: {
  caseRow: CaseWithOpens
  muted?: boolean
}) {
  const overdue = isOverdue(caseRow.status, caseRow.due_date)
  return (
    <Link
      to={`/trainee/cases/${caseRow.id}`}
      className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 transition hover:border-primary/40 ${
        muted
          ? 'border-border/70 bg-bg'
          : 'border-border bg-surface'
      }`}
    >
      <div>
        <p className="font-medium text-text">{caseLabel(caseRow)}</p>
        <p className="text-sm text-muted">
          {shortTraineeStep(caseRow.status)}
          {caseRow.openCorrections > 0
            ? ` · ${caseRow.openCorrections} correction${caseRow.openCorrections === 1 ? '' : 's'}`
            : ''}
          {overdue ? ' · Overdue' : ''}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <span className={`text-sm ${overdue ? 'text-danger' : 'text-muted'}`}>
          {formatDue(caseRow.due_date)}
        </span>
        <StatusBadge status={caseRow.status} />
      </div>
    </Link>
  )
}
