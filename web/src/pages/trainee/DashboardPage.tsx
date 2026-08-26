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
import { getTraineeForUser, listCases } from '@/lib/api'
import { caseLabel, casePhaseNo } from '@/lib/domain/caseLabels'
import {
  caseOwner,
  formatDue,
  isOverdue,
  nextStep,
  TRAINEE_OWNED_STATUSES,
} from '@/lib/domain/ownership'
import type { CaseRow } from '@/lib/types'

export function TraineeDashboardPage() {
  const { user } = useAuth()
  const [phase, setPhase] = useState<1 | 2 | 'all'>('all')
  // Defaults to the actionable subset, not the full history — a trainee
  // with 30+ approved cases was seeing all of them before the handful that
  // actually need attention (audit: "opens on all 56, not the 10 that need
  // Aaron"). "All" stays one click away.
  const [scope, setScope] = useState<'needs_you' | 'all'>('needs_you')

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
        // Visibility is status-driven (assigned+), not released_on — gotchas #1/#6.
      }),
    enabled: !!traineeQ.data?.id,
  })

  const visibleCases = useMemo(() => {
    const rows = casesQ.data ?? []
    // Trainee never sees not_started (trainer-owned until assigned).
    const visible = rows.filter((c) => c.status !== 'not_started')
    if (phase === 'all') return visible
    return visible.filter((c) => casePhaseNo(c) === phase)
  }, [casesQ.data, phase])

  const cases = useMemo(() => {
    if (scope === 'all') return visibleCases
    return visibleCases.filter((c) => TRAINEE_OWNED_STATUSES.has(c.status))
  }, [visibleCases, scope])

  // These read from the full visible set, not the scoped `cases` list, so
  // the KPI row stays constant regardless of which scope tab is selected.
  const nextUp = useMemo(() => {
    return (
      visibleCases.find((c) => TRAINEE_OWNED_STATUSES.has(c.status)) ??
      visibleCases.find((c) => caseOwner(c.status) === 'trainee') ??
      null
    )
  }, [visibleCases])

  const ownedCount = visibleCases.filter((c) =>
    TRAINEE_OWNED_STATUSES.has(c.status),
  ).length
  const overdueCount = visibleCases.filter((c) =>
    isOverdue(c.status, c.due_date),
  ).length
  const approvedCount = visibleCases.filter((c) => c.status === 'approved').length
  const inReviewCount = visibleCases.filter(
    (c) => c.status === 'in_review' || c.status === 'corrections_sent',
  ).length

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
    <div>
      <PageHeader
        title="My cases"
        description={`Hello ${traineeQ.data.full_name}. Status, due date, and next action for every open case.`}
      />

      <MetricsRow
        items={[
          { label: 'Needs you', value: ownedCount },
          { label: 'Overdue', value: overdueCount },
          { label: 'In review', value: inReviewCount },
          { label: 'Approved', value: approvedCount },
        ]}
      />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-md border border-border bg-surface p-1">
          {(
            [
              ['needs_you', 'Needs you'],
              ['all', 'All cases'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setScope(value)}
              className={`rounded px-3 py-1.5 text-sm transition-colors duration-150 ${
                scope === value
                  ? 'bg-primary text-primary-fg'
                  : 'text-muted hover:text-text'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

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
      </div>

      <div className="mt-6">
        {nextUp ? (
          <NextStepCallout title="Up next">
            <Link
              to={`/trainee/cases/${nextUp.id}`}
              className="font-medium text-primary underline-offset-2 hover:underline"
            >
              {caseLabel(nextUp)}
            </Link>
            <span className="text-muted">
              {' '}
              — {nextStep(nextUp.status, 'trainee')} · due{' '}
              {formatDue(nextUp.due_date)}
            </span>
          </NextStepCallout>
        ) : (
          <NextStepCallout title="All caught up">
            Nothing waiting on you right now. Cases appear here once your
            trainer assigns them.
          </NextStepCallout>
        )}
      </div>

      {visibleCases.length > 0 ? (
        <div className="mt-6">
          <h2 className="mb-3 text-lg font-semibold">Your progress</h2>
          <TrainingJourney cases={visibleCases} />
        </div>
      ) : null}

      <div key={scope} className="fade-in mt-6 space-y-2">
        {cases.length === 0 ? (
          <EmptyState
            title={
              scope === 'needs_you' && visibleCases.length > 0
                ? 'Nothing needs you right now'
                : 'No cases yet'
            }
            description={
              scope === 'needs_you' && visibleCases.length > 0
                ? 'Switch to "All cases" to see cases in review or already approved.'
                : 'When your trainer assigns a case, it will show up here.'
            }
          />
        ) : (
          cases.map((c) => <CaseListRow key={c.id} caseRow={c} />)
        )}
      </div>
    </div>
  )
}

function CaseListRow({ caseRow }: { caseRow: CaseRow }) {
  const overdue = isOverdue(caseRow.status, caseRow.due_date)
  return (
    <Link
      to={`/trainee/cases/${caseRow.id}`}
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3 transition hover:border-primary/40"
    >
      <div>
        <p className="font-medium text-text">{caseLabel(caseRow)}</p>
        <p className="text-sm text-muted">
          {nextStep(caseRow.status, 'trainee')}
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
