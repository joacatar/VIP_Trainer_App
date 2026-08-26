import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { EmptyState } from '@/components/ui/EmptyState'
import { MetricsRow } from '@/components/ui/MetricsRow'
import { PageHeader } from '@/components/ui/PageHeader'
import { ProgressRing } from '@/components/ui/ProgressRing'
import {
  listActiveTrainees,
  listProgress,
  listQuestionsForTrainer,
} from '@/lib/api'

export function TrainerDashboardPage() {
  const progressQ = useQuery({
    queryKey: ['progress'],
    queryFn: listProgress,
  })
  const traineesQ = useQuery({
    queryKey: ['trainees'],
    queryFn: listActiveTrainees,
  })
  const questionsQ = useQuery({
    queryKey: ['trainer-questions'],
    queryFn: listQuestionsForTrainer,
  })

  const realProgress = useMemo(
    () => (progressQ.data ?? []).filter((p) => !p.is_test),
    [progressQ.data],
  )

  const totals = useMemo(() => {
    return realProgress.reduce(
      (acc, p) => ({
        overdue: acc.overdue + (p.overdue_cases ?? 0),
        waitingTrainer: acc.waitingTrainer + (p.waiting_on_trainer ?? 0),
        waitingTrainee: acc.waitingTrainee + (p.waiting_on_trainee ?? 0),
        openQuestions: acc.openQuestions,
      }),
      {
        overdue: 0,
        waitingTrainer: 0,
        waitingTrainee: 0,
        openQuestions: (questionsQ.data ?? []).filter((q) => q.status === 'open')
          .length,
      },
    )
  }, [realProgress, questionsQ.data])

  const needsAttention = useMemo(() => {
    return [...realProgress]
      .filter(
        (p) =>
          (p.overdue_cases ?? 0) > 0 ||
          (p.waiting_on_trainer ?? 0) > 0 ||
          (p.waiting_on_trainee ?? 0) > 0,
      )
      .sort(
        (a, b) =>
          (b.overdue_cases ?? 0) - (a.overdue_cases ?? 0) ||
          (b.waiting_on_trainer ?? 0) - (a.waiting_on_trainer ?? 0),
      )
      .slice(0, 8)
  }, [realProgress])

  return (
    <div className="space-y-8">
      <PageHeader
        title="Today’s training work"
        description="What needs a decision now — reviews, overdue cases, and open questions."
      />

      <MetricsRow
        items={[
          { label: 'Needs review', value: totals.waitingTrainer },
          { label: 'Overdue', value: totals.overdue },
          { label: 'Awaiting trainee', value: totals.waitingTrainee },
          { label: 'Open questions', value: totals.openQuestions },
        ]}
      />

      <Link
        to="/trainer/analytics"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
      >
        See what repeats across every trainee →
      </Link>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Needs attention</h2>
        {needsAttention.length === 0 ? (
          <EmptyState
            title="Inbox clear"
            description="No overdue cases or packages waiting on you."
          />
        ) : (
          <ul className="space-y-2">
            {needsAttention.map((p) => (
              <li
                key={p.trainee_id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3"
              >
                <div>
                  <p className="font-medium">{p.full_name}</p>
                  <p className="text-sm text-muted">
                    {(p.overdue_cases ?? 0) > 0
                      ? `${p.overdue_cases} overdue`
                      : null}
                    {(p.waiting_on_trainer ?? 0) > 0
                      ? `${(p.overdue_cases ?? 0) > 0 ? ' · ' : ''}${p.waiting_on_trainer} need review`
                      : null}
                    {(p.waiting_on_trainee ?? 0) > 0
                      ? ` · ${p.waiting_on_trainee} waiting on trainee`
                      : null}
                  </p>
                </div>
                <Link
                  to={`/trainer/cases?trainee=${p.trainee_id}`}
                  className="text-sm font-medium text-primary hover:underline"
                >
                  Open cases
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Open questions</h2>
        {(questionsQ.data ?? []).filter((q) => q.status === 'open').length ===
        0 ? (
          <p className="text-sm text-muted">No open questions.</p>
        ) : (
          <ul className="space-y-2">
            {(questionsQ.data ?? [])
              .filter((q) => q.status === 'open')
              .slice(0, 6)
              .map((q) => (
                <li
                  key={q.id}
                  className="rounded-lg border border-border bg-surface px-4 py-3 text-sm"
                >
                  <p className="font-medium">{q.body}</p>
                  <Link
                    to={`/trainer/cases/${q.case_id}`}
                    className="mt-1 inline-block text-primary hover:underline"
                  >
                    Answer in case
                  </Link>
                </li>
              ))}
          </ul>
        )}
      </section>

      <section>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold">Trainee progress</h2>
          <span
            className="rounded-full border border-attention/40 bg-attention/10 px-2 py-0.5 text-xs font-medium text-attention"
            title="Recomputed while phase 2 was being built and validated today — cross-check anything you're about to act on."
          >
            Beta — verify before relying on this
          </span>
        </div>
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-border bg-surface-2 text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-2 font-medium">Trainee</th>
                <th className="px-4 py-2 font-medium">Approved</th>
                <th className="px-4 py-2 font-medium">Phase 2</th>
                <th className="px-4 py-2 font-medium">Overdue</th>
              </tr>
            </thead>
            <tbody>
              {realProgress.map((p) => (
                <tr key={p.trainee_id} className="border-b border-border/70">
                  <td className="px-4 py-2 font-medium">{p.full_name}</td>
                  <td className="px-4 py-2">
                    <ProgressRing value={p.approved_cases} total={p.total_cases} />
                  </td>
                  <td className="px-4 py-2 tabular-nums">
                    {p.phase_2_started_on
                      ? `${p.phase_2_approved}/${p.phase_2_cases}`
                      : '—'}
                  </td>
                  <td className="px-4 py-2 tabular-nums">{p.overdue_cases}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(traineesQ.data?.length ?? 0) === 0 ? (
          <p className="mt-2 text-sm text-muted">No active trainees yet.</p>
        ) : null}
      </section>
    </div>
  )
}
