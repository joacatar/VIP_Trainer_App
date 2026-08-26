import { useMemo, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageHeader } from '@/components/ui/PageHeader'
import { SkeletonRows } from '@/components/ui/Skeleton'
import { StatusBadge } from '@/components/ui/StatusBadge'
import {
  assignHomework,
  listActiveTrainees,
  listCases,
} from '@/lib/api'
import { caseLabel, casePhaseNo } from '@/lib/domain/caseLabels'
import {
  attentionState,
  formatDue,
  isOverdue,
  nextStep,
} from '@/lib/domain/ownership'
import type { AttentionState, CaseRow } from '@/lib/types'

const LANES: Array<{ key: AttentionState; title: string }> = [
  { key: 'assigned', title: 'Needs assignment' },
  { key: 'with_trainee', title: 'With trainee' },
  { key: 'needs_trainer', title: 'Needs you' },
  { key: 'approved', title: 'Approved' },
]

export function TrainerCasesPage() {
  const [params, setParams] = useSearchParams()
  const traineeId = params.get('trainee') ?? ''
  const view = params.get('view') === 'inbox' ? 'inbox' : 'board'
  const [phase, setPhase] = useState<1 | 2 | 'all'>('all')
  const [assignCaseId, setAssignCaseId] = useState<string | null>(null)
  const [dueDate, setDueDate] = useState('')
  const [instructions, setInstructions] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const qc = useQueryClient()

  const traineesQ = useQuery({
    queryKey: ['trainees'],
    queryFn: listActiveTrainees,
  })

  const selected =
    traineesQ.data?.find((t) => t.id === traineeId) ??
    traineesQ.data?.find((t) => !t.is_test) ??
    traineesQ.data?.[0]

  const casesQ = useQuery({
    queryKey: ['trainer-cases', selected?.id],
    queryFn: () =>
      listCases(selected!.id, { includeFiles: true, includeSource: true }),
    enabled: !!selected?.id,
  })

  const cases = useMemo(() => {
    const rows = casesQ.data ?? []
    if (phase === 'all') return rows
    return rows.filter((c) => casePhaseNo(c) === phase)
  }, [casesQ.data, phase])

  const byLane = useMemo(() => {
    const map: Record<AttentionState, CaseRow[]> = {
      assigned: [],
      with_trainee: [],
      needs_trainer: [],
      approved: [],
    }
    for (const c of cases) {
      map[attentionState(c.status)].push(c)
    }
    return map
  }, [cases])

  const assign = useMutation({
    mutationFn: async () => {
      if (!assignCaseId || !dueDate) throw new Error('Pick a due date')
      const c = cases.find((x) => x.id === assignCaseId)
      return assignHomework({
        caseId: assignCaseId,
        title: c ? caseLabel(c) : 'Case assignment',
        instructions: instructions.trim() || 'Complete the three deliverables.',
        scheduleDueDate: c?.schedule_due_date ?? dueDate,
        dueDate,
      })
    },
    onSuccess: () => {
      setMsg('Case assigned.')
      setAssignCaseId(null)
      setInstructions('')
      void qc.invalidateQueries({ queryKey: ['trainer-cases', selected?.id] })
    },
    onError: (e: Error) => setMsg(e.message),
  })

  const hasPhase2 = !!selected?.phase_2_started_on

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cases"
        description="Board and inbox across phase 1 and live cases. Assignment is always explicit."
      />

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-muted">Trainee</span>
          <select
            className="rounded-md border border-border bg-surface px-3 py-2"
            value={selected?.id ?? ''}
            onChange={(e) => {
              const next = new URLSearchParams(params)
              next.set('trainee', e.target.value)
              setParams(next)
            }}
          >
            {(traineesQ.data ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.full_name}
                {t.is_test ? ' (test)' : ''}
              </option>
            ))}
          </select>
        </label>

        <div className="inline-flex rounded-md border border-border bg-surface p-1">
          {(
            [
              ['board', 'Board'],
              ['inbox', 'Inbox'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={`rounded px-3 py-1.5 text-sm transition-colors duration-150 ${
                view === value
                  ? 'bg-primary text-primary-fg'
                  : 'text-muted hover:text-text'
              }`}
              onClick={() => {
                const next = new URLSearchParams(params)
                next.set('view', value)
                setParams(next)
              }}
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

      {msg ? (
        <p className="rounded-md border border-border bg-surface-2 px-3 py-2 text-sm">
          {msg}
        </p>
      ) : null}

      {!selected ? (
        <EmptyState title="No trainees" description="Add a trainee first." />
      ) : casesQ.isLoading ? (
        <SkeletonRows count={4} />
      ) : view === 'board' ? (
        <div className="grid gap-3 lg:grid-cols-4">
          {LANES.map((lane) => (
            <div
              key={lane.key}
              className="rounded-lg border border-border bg-surface p-3"
            >
              <h3 className="mb-2 text-sm font-semibold">
                {lane.title}{' '}
                <span className="text-muted">({byLane[lane.key].length})</span>
              </h3>
              <ul className="space-y-2">
                {byLane[lane.key].map((c) => (
                  <li
                    key={c.id}
                    className="rounded-md border border-border bg-bg p-2 text-sm"
                  >
                    <Link
                      to={`/trainer/cases/${c.id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {caseLabel(c)}
                    </Link>
                    <p className="mt-1 text-xs text-muted">
                      {formatDue(c.due_date)}
                      {isOverdue(c.status, c.due_date) ? ' · Overdue' : ''}
                    </p>
                    {c.status === 'not_started' ? (
                      <Button
                        className="mt-2"
                        variant="secondary"
                        onClick={() => {
                          setAssignCaseId(c.id)
                          setDueDate(c.schedule_due_date ?? c.due_date ?? '')
                        }}
                      >
                        Assign
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <ul className="space-y-2">
          {cases.map((c) => (
            <li
              key={c.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3"
            >
              <div>
                <Link
                  to={`/trainer/cases/${c.id}`}
                  className="font-medium text-primary hover:underline"
                >
                  {caseLabel(c)}
                </Link>
                <p className="text-sm text-muted">
                  {nextStep(c.status, 'trainer')}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted">{formatDue(c.due_date)}</span>
                <StatusBadge status={c.status} />
                {c.status === 'not_started' ? (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setAssignCaseId(c.id)
                      setDueDate(c.schedule_due_date ?? c.due_date ?? '')
                    }}
                  >
                    Assign
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}

      {assignCaseId ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form
            className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-lg"
            onSubmit={(e: FormEvent) => {
              e.preventDefault()
              assign.mutate()
            }}
          >
            <h3 className="text-lg font-semibold">Assign case</h3>
            <p className="mt-1 text-sm text-muted">
              Uses the assign_homework RPC — the only valid path out of
              not_started.
            </p>
            <label className="mt-4 block text-sm">
              Due date
              <input
                type="date"
                required
                className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </label>
            <label className="mt-3 block text-sm">
              Instructions
              <textarea
                className="mt-1 min-h-20 w-full rounded-md border border-border bg-bg px-3 py-2"
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
              />
            </label>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setAssignCaseId(null)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={assign.isPending}>
                Assign
              </Button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  )
}
