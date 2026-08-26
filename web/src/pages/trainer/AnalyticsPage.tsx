import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { EmptyState } from '@/components/ui/EmptyState'
import { MetricsRow } from '@/components/ui/MetricsRow'
import { PageHeader } from '@/components/ui/PageHeader'
import { SkeletonRows } from '@/components/ui/Skeleton'
import { listActiveTrainees, listAllRaisedCorrections } from '@/lib/api'
import {
  flattenCorrections,
  FOCUS_AREA_COUNT,
  FOCUS_AREA_PLAN,
  groupRepeated,
  resolutionStats,
  sectionBreakdown,
  type FlatCorrection,
} from '@/lib/domain/correctionAnalytics'

function fmtDate(iso: string): string {
  return iso.slice(0, 10)
}

export function TrainerAnalyticsPage() {
  const [scope, setScope] = useState<'overall' | 'trainee'>('overall')
  const [traineeId, setTraineeId] = useState<string>('')

  const correctionsQ = useQuery({
    queryKey: ['all-raised-corrections'],
    queryFn: listAllRaisedCorrections,
  })
  const traineesQ = useQuery({
    queryKey: ['trainees'],
    queryFn: listActiveTrainees,
  })

  const realTrainees = useMemo(
    () => (traineesQ.data ?? []).filter((t) => !t.is_test),
    [traineesQ.data],
  )
  const realTraineeIds = useMemo(
    () => new Set(realTrainees.map((t) => t.id)),
    [realTrainees],
  )

  // Drop test/dummy trainees from the aggregate the same way the trainer
  // dashboard's own progress table already does (realProgress) — otherwise
  // a demo trainee's corrections silently skew "what repeats" for everyone.
  const flat = useMemo(() => {
    const all = flattenCorrections(correctionsQ.data ?? [])
    return all.filter((c) => realTraineeIds.has(c.traineeId))
  }, [correctionsQ.data, realTraineeIds])

  const selected =
    realTrainees.find((t) => t.id === traineeId) ?? realTrainees[0] ?? null

  const scoped: FlatCorrection[] = useMemo(() => {
    if (scope === 'overall') return flat
    if (!selected) return []
    return flat.filter((c) => c.traineeId === selected.id)
  }, [flat, scope, selected])

  const repeated = useMemo(() => groupRepeated(scoped, 2), [scoped])
  const focusAreas = repeated.slice(0, FOCUS_AREA_COUNT)
  const otherRepeated = repeated.slice(FOCUS_AREA_COUNT)
  const bySection = useMemo(() => sectionBreakdown(scoped), [scoped])
  const stats = useMemo(() => resolutionStats(scoped), [scoped])
  const maxSection = bySection[0]?.count ?? 1

  const isLoading = correctionsQ.isLoading || traineesQ.isLoading

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <PageHeader
          title="Analytics"
          description="What repeats across corrections — a checklist chip that keeps getting used probably needs to be fixed at the source, not corrected by hand every time."
        />
        <span
          className="mb-1 rounded-full border border-attention/40 bg-attention/10 px-2 py-0.5 text-xs font-medium text-attention"
          title="First pass at this view — cross-check patterns against the real cases before changing a checklist chip because of them."
        >
          Beta — verify before relying on this
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-md border border-border bg-surface p-1">
          {(
            [
              ['overall', 'Overall'],
              ['trainee', 'By trainee'],
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

        {scope === 'trainee' ? (
          <select
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm"
            value={selected?.id ?? ''}
            onChange={(e) => setTraineeId(e.target.value)}
          >
            {realTrainees.map((t) => (
              <option key={t.id} value={t.id}>
                {t.full_name}
              </option>
            ))}
          </select>
        ) : null}
      </div>

      {isLoading ? (
        <SkeletonRows count={4} />
      ) : scoped.length === 0 ? (
        <EmptyState
          title="No corrections yet"
          description={
            scope === 'trainee'
              ? 'This trainee has no corrections on record.'
              : 'Corrections raised on any case will show up here.'
          }
        />
      ) : (
        <>
          <MetricsRow
            items={[
              { label: 'Corrections raised', value: scoped.length },
              { label: 'Repeated patterns', value: repeated.length },
              {
                label: 'Most active section',
                value: bySection[0]?.label ?? '—',
              },
              {
                label: 'Resolution rate',
                value: `${Math.round(stats.resolutionRate * 100)}%`,
                hint: `${stats.resolvedThreads}/${stats.totalThreads} threads`,
              },
            ]}
          />

          {focusAreas.length > 0 ? (
            <section>
              <h2 className="mb-1 text-lg font-semibold">Focus areas</h2>
              <p className="mb-3 text-sm text-muted">
                The top {FOCUS_AREA_COUNT} most repeated corrections{' '}
                {scope === 'overall' ? 'across trainees' : 'for this trainee'}
                . We're building real resources for these instead of just
                correcting them by hand each time.
              </p>
              <ul className="space-y-3">
                {focusAreas.map((g) => (
                  <li
                    key={g.key}
                    className="fade-in rounded-md border-2 border-primary/40 bg-primary/5 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <span className="text-xs font-medium uppercase tracking-wide text-primary">
                          {g.sectionLabel} · Focus area
                        </span>
                        <p className="mt-0.5 font-medium text-text">
                          {g.body}
                        </p>
                      </div>
                      <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                        {g.count}×
                      </span>
                    </div>
                    {scope === 'overall' ? (
                      <p className="mt-1 text-xs text-muted">
                        {g.traineeNames.join(', ')}
                      </p>
                    ) : null}

                    <div className="mt-3 rounded-md bg-surface-2 p-3">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted">
                        Building resources for this
                      </p>
                      <ul className="mt-1.5 space-y-1 text-sm text-text">
                        {FOCUS_AREA_PLAN.map((step) => (
                          <li key={step} className="flex items-center gap-2">
                            <span
                              aria-hidden="true"
                              className="inline-block h-3.5 w-3.5 shrink-0 rounded-sm border border-muted"
                            />
                            {step}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <details className="mt-2 text-xs text-muted">
                      <summary className="cursor-pointer select-none hover:text-text">
                        Where ({g.occurrences.length})
                      </summary>
                      <ul className="mt-1.5 space-y-1">
                        {g.occurrences.map((o) => (
                          <li key={o.id}>
                            <Link
                              to={`/trainer/cases/${o.caseId}`}
                              className="text-primary hover:underline"
                            >
                              {o.caseLabel}
                            </Link>
                            {scope === 'overall' ? ` · ${o.traineeName}` : ''}
                            {' · '}
                            {fmtDate(o.createdAt)}
                          </li>
                        ))}
                      </ul>
                    </details>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section>
            <h2 className="mb-1 text-lg font-semibold">
              Also repeating
            </h2>
            <p className="mb-3 text-sm text-muted">
              Raised 2 or more times{' '}
              {scope === 'overall' ? 'across trainees' : 'for this trainee'},
              most frequent first — not a focus area yet.
            </p>
            {otherRepeated.length === 0 ? (
              <p className="text-sm text-muted">
                {repeated.length === 0
                  ? 'Nothing repeats yet — every correction so far has been distinct.'
                  : 'Nothing else repeats yet — the focus areas above are the only patterns so far.'}
              </p>
            ) : (
              <ul className="space-y-3">
                {otherRepeated.slice(0, 15).map((g) => (
                  <li
                    key={g.key}
                    className="fade-in rounded-md border border-l-4 border-border border-l-attention bg-surface p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <span className="text-xs font-medium uppercase tracking-wide text-muted">
                          {g.sectionLabel}
                        </span>
                        <p className="mt-0.5 font-medium text-text">
                          {g.body}
                        </p>
                      </div>
                      <span className="shrink-0 rounded-full bg-attention/10 px-2 py-0.5 text-xs font-semibold text-attention">
                        {g.count}×
                      </span>
                    </div>
                    {scope === 'overall' ? (
                      <p className="mt-1 text-xs text-muted">
                        {g.traineeNames.join(', ')}
                      </p>
                    ) : null}
                    <details className="mt-2 text-xs text-muted">
                      <summary className="cursor-pointer select-none hover:text-text">
                        Where ({g.occurrences.length})
                      </summary>
                      <ul className="mt-1.5 space-y-1">
                        {g.occurrences.map((o) => (
                          <li key={o.id}>
                            <Link
                              to={`/trainer/cases/${o.caseId}`}
                              className="text-primary hover:underline"
                            >
                              {o.caseLabel}
                            </Link>
                            {scope === 'overall' ? ` · ${o.traineeName}` : ''}
                            {' · '}
                            {fmtDate(o.createdAt)}
                          </li>
                        ))}
                      </ul>
                    </details>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">By section</h2>
            <div className="space-y-2 rounded-lg border border-border bg-surface p-4">
              {bySection.map((b) => (
                <div key={b.key} className="flex items-center gap-3">
                  <span className="w-36 shrink-0 text-sm text-muted">
                    {b.label}
                  </span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${(b.count / maxSection) * 100}%` }}
                    />
                  </div>
                  <span className="w-8 shrink-0 text-right text-sm tabular-nums text-muted">
                    {b.count}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
