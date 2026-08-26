import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { EmptyState } from '@/components/ui/EmptyState'
import { MetricsRow } from '@/components/ui/MetricsRow'
import { PageHeader } from '@/components/ui/PageHeader'
import { SkeletonRows } from '@/components/ui/Skeleton'
import { useAuth } from '@/hooks/useAuth'
import {
  getTraineeForUser,
  listCases,
  listRaisedCorrectionsForCases,
} from '@/lib/api'
import {
  flattenCorrections,
  FOCUS_AREA_COUNT,
  groupRepeated,
  resolutionStats,
} from '@/lib/domain/correctionAnalytics'
import { THREAD_STATUS_LABELS } from '@/lib/domain/revisions'

function fmtDate(iso: string): string {
  return iso.slice(0, 10)
}

export function TraineeCorrectionsPage() {
  const { user } = useAuth()
  const traineeQ = useQuery({
    queryKey: ['trainee-for-user', user?.id],
    queryFn: () => getTraineeForUser(user!.id),
    enabled: !!user,
  })
  const casesQ = useQuery({
    queryKey: ['trainee-cases-lite', traineeQ.data?.id],
    queryFn: () => listCases(traineeQ.data!.id),
    enabled: !!traineeQ.data?.id,
  })
  const caseIds = useMemo(
    () => (casesQ.data ?? []).map((c) => c.id),
    [casesQ.data],
  )
  const correctionsQ = useQuery({
    queryKey: ['my-raised-corrections', traineeQ.data?.id, caseIds.length],
    queryFn: () => listRaisedCorrectionsForCases(caseIds),
    enabled: !!traineeQ.data?.id && caseIds.length > 0,
  })

  const flat = useMemo(
    () => flattenCorrections(correctionsQ.data ?? []),
    [correctionsQ.data],
  )
  const repeated = useMemo(() => groupRepeated(flat, 2), [flat])
  const stats = useMemo(() => resolutionStats(flat), [flat])
  const chronological = useMemo(
    () => [...flat].sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
    [flat],
  )

  const isLoading =
    traineeQ.isLoading || casesQ.isLoading || correctionsQ.isLoading

  if (isLoading) return <SkeletonRows count={4} />

  return (
    <div className="space-y-6">
      <PageHeader
        title="My corrections"
        description="Feedback across every case you've submitted — the ones that repeat are worth remembering for the next one."
      />

      {flat.length === 0 ? (
        <EmptyState
          title="No corrections yet"
          description="Once your trainer reviews a case and publishes feedback, it shows up here."
        />
      ) : (
        <>
          <MetricsRow
            items={[
              { label: 'Received', value: flat.length },
              { label: 'Repeated', value: repeated.length },
              { label: 'Resolved', value: stats.resolvedThreads },
              {
                label: 'Open',
                value: stats.totalThreads - stats.resolvedThreads,
              },
            ]}
          />

          <section>
            <h2 className="mb-1 text-lg font-semibold">Keeps coming back</h2>
            <p className="mb-3 text-sm text-muted">
              Corrections you've gotten 2 or more times, most frequent first
              — worth double-checking on your next case before you submit.
            </p>
            {repeated.length === 0 ? (
              <p className="text-sm text-muted">
                Nothing repeats yet — every correction so far has been
                different.
              </p>
            ) : (
              <ul className="space-y-3">
                {repeated.map((g, i) => {
                  const isFocus = i < FOCUS_AREA_COUNT
                  return (
                    <li
                      key={g.key}
                      className={`fade-in rounded-md border p-4 ${
                        isFocus
                          ? 'border-2 border-primary/40 bg-primary/5'
                          : 'border-l-4 border-border border-l-attention bg-surface'
                      }`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <span
                            className={`text-xs font-medium uppercase tracking-wide ${isFocus ? 'text-primary' : 'text-muted'}`}
                          >
                            {g.sectionLabel}
                          </span>
                          <p className="mt-0.5 font-medium text-text">
                            {g.body}
                          </p>
                        </div>
                        <span
                          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
                            isFocus
                              ? 'bg-primary/10 text-primary'
                              : 'bg-attention/10 text-attention'
                          }`}
                        >
                          {g.count}×
                        </span>
                      </div>
                      <p className="mt-2 flex flex-wrap gap-x-1.5 gap-y-1 text-xs text-muted">
                        {g.occurrences.map((o, i2) => (
                          <span key={o.id}>
                            <Link
                              to={`/trainee/cases/${o.caseId}`}
                              className="text-primary hover:underline"
                            >
                              {o.caseLabel}
                            </Link>
                            {i2 < g.occurrences.length - 1 ? ',' : ''}
                          </span>
                        ))}
                      </p>
                      {isFocus ? (
                        <p className="mt-2 text-xs font-medium text-primary">
                          📌 Your trainer is building resources to help with
                          this.
                        </p>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">All corrections</h2>
            <ul className="space-y-2">
              {chronological.map((c) => (
                <li
                  key={c.id}
                  className="rounded-lg border border-border bg-surface px-4 py-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <span className="text-xs font-medium uppercase tracking-wide text-muted">
                        {c.sectionLabel}
                      </span>
                      <p className="mt-0.5 text-sm text-text">{c.body}</p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${
                        c.threadStatus === 'resolved'
                          ? 'border-success/30 bg-success/10 text-success'
                          : 'border-attention/30 bg-attention/10 text-attention'
                      }`}
                    >
                      {THREAD_STATUS_LABELS[c.threadStatus] ?? c.threadStatus}
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs text-muted">
                    <Link
                      to={`/trainee/cases/${c.caseId}`}
                      className="text-primary hover:underline"
                    >
                      {c.caseLabel}
                    </Link>
                    {' · '}
                    {fmtDate(c.createdAt)}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  )
}
