import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageHeader } from '@/components/ui/PageHeader'
import { SkeletonRows } from '@/components/ui/Skeleton'
import { StatusBadge } from '@/components/ui/StatusBadge'
import {
  assignHomeworkBatch,
  listActiveTrainees,
  listTrainerQueue,
} from '@/lib/api'
import { caseLabel, casePhaseNo } from '@/lib/domain/caseLabels'
import {
  daysSince,
  formatShortDateTime,
  formatWaitingAge,
  isUnchecked,
  nextStep,
} from '@/lib/domain/ownership'
import type { CaseRow } from '@/lib/types'

type Tab = 'needs_you' | 'assign' | 'with_trainee' | 'approved'
type WaitingFilter = 'all' | 'ready' | 'unchecked' | 'gt1' | 'gt3'
type PhaseFilter = 'all' | 1 | 2

const TABS: Array<{ key: Tab; label: string }> = [
  { key: 'needs_you', label: 'Needs you' },
  { key: 'assign', label: 'Assign' },
  { key: 'with_trainee', label: 'With trainee' },
  { key: 'approved', label: 'Approved' },
]

function defaultDueDate(): string {
  const d = new Date()
  d.setDate(d.getDate() + 3)
  return d.toISOString().slice(0, 10)
}

/**
 * Trainer cases home — Needs you queue + tabs. No kanban.
 */
export function TrainerCasesPage() {
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as Tab) || 'needs_you'
  const traineeFilter = params.get('trainee') ?? ''
  const [phase, setPhase] = useState<PhaseFilter>('all')
  const [waiting, setWaiting] = useState<WaitingFilter>('all')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [dueDate, setDueDate] = useState(defaultDueDate)
  const [instructions, setInstructions] = useState(
    'Complete the three deliverables.',
  )
  const [msg, setMsg] = useState<string | null>(null)
  const qc = useQueryClient()

  const traineesQ = useQuery({
    queryKey: ['trainees'],
    queryFn: listActiveTrainees,
  })

  const queueQ = useQuery({
    queryKey: ['trainer-queue', tab, traineeFilter || null],
    queryFn: () =>
      listTrainerQueue({
        tab: TABS.some((t) => t.key === tab) ? tab : 'needs_you',
        traineeId: traineeFilter || null,
      }),
  })

  const rows = useMemo(() => {
    let list = queueQ.data ?? []
    if (phase !== 'all') {
      list = list.filter((c) => casePhaseNo(c) === phase)
    }
    if (tab === 'needs_you') {
      if (waiting === 'ready') {
        list = list.filter((c) => c.status === 'in_review')
      } else if (waiting === 'unchecked') {
        list = list.filter((c) =>
          isUnchecked(c.received_at, c.trainer_last_opened_at),
        )
      } else if (waiting === 'gt1') {
        list = list.filter((c) => (daysSince(c.received_at) ?? -1) > 1)
      } else if (waiting === 'gt3') {
        list = list.filter((c) => (daysSince(c.received_at) ?? -1) > 3)
      }
    }
    // Hide test trainees from default Needs you unless filtered to them
    if (!traineeFilter) {
      list = list.filter((c) => !c.trainee_is_test)
    }
    return list
  }, [queueQ.data, phase, waiting, tab, traineeFilter])

  const assignCandidates = useMemo(() => {
    if (tab !== 'assign') return []
    return [...rows].sort((a, b) => {
      const pa = a.phase_no - b.phase_no
      if (pa !== 0) return pa
      const ra = (a.released_on ?? '').localeCompare(b.released_on ?? '')
      if (ra !== 0) return ra
      return a.case_no - b.case_no
    })
  }, [rows, tab])

  const setTab = (next: Tab) => {
    const p = new URLSearchParams(params)
    p.set('tab', next)
    setParams(p)
    setSelected(new Set())
    setMsg(null)
  }

  const setTrainee = (id: string) => {
    const p = new URLSearchParams(params)
    if (id) p.set('trainee', id)
    else p.delete('trainee')
    setParams(p)
    setSelected(new Set())
  }

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectNext5 = () => {
    const ids = assignCandidates.slice(0, 5).map((c) => c.id)
    setSelected(new Set(ids))
    const first = assignCandidates[0]
    if (first?.schedule_due_date) setDueDate(first.schedule_due_date)
    else if (first?.due_date) setDueDate(first.due_date)
  }

  const bulkAssign = useMutation({
    mutationFn: async () => {
      if (!dueDate) throw new Error('Pick a due date')
      const picked = assignCandidates.filter((c) => selected.has(c.id))
      if (picked.length === 0) throw new Error('Select at least one case')
      return assignHomeworkBatch(
        picked.map((c) => ({
          caseId: c.id,
          title: caseLabel(c),
          instructions: instructions.trim() || 'Complete the three deliverables.',
          scheduleDueDate: c.schedule_due_date ?? dueDate,
          dueDate,
        })),
      )
    },
    onSuccess: (result) => {
      setMsg(
        result.failed.length === 0
          ? `Assigned ${result.ok.length} case(s).`
          : `Assigned ${result.ok.length}; ${result.failed.length} failed.`,
      )
      setSelected(new Set())
      void qc.invalidateQueries({ queryKey: ['trainer-queue'] })
      void qc.invalidateQueries({ queryKey: ['progress'] })
    },
    onError: (e: Error) => setMsg(e.message),
  })

  const hasAnyPhase2 = (traineesQ.data ?? []).some((t) => t.phase_2_started_on)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cases"
        description="Needs you first — open, approve or send one correction. Assign in bulk when ready."
      />

      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${
              tab === t.key
                ? 'bg-primary text-primary-fg'
                : 'text-muted hover:bg-surface-2 hover:text-text'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-muted">Trainee</span>
          <select
            className="rounded-md border border-border bg-surface px-3 py-2"
            value={traineeFilter}
            onChange={(e) => setTrainee(e.target.value)}
          >
            <option value="">All trainees</option>
            {(traineesQ.data ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.full_name}
                {t.is_test ? ' (test)' : ''}
              </option>
            ))}
          </select>
        </label>

        {hasAnyPhase2 ? (
          <div className="inline-flex rounded-md border border-border bg-surface p-1">
            {(
              [
                ['all', 'All phases'],
                [1, 'Phase 1'],
                [2, 'Live'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={label}
                type="button"
                onClick={() => setPhase(value)}
                className={`rounded px-3 py-1.5 text-sm ${
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

      {tab === 'needs_you' ? (
        <div className="flex flex-wrap gap-2">
          {(
            [
              ['all', 'All'],
              ['ready', 'Ready to review'],
              ['unchecked', 'Unchecked'],
              ['gt1', 'Waiting >1d'],
              ['gt3', 'Waiting >3d'],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setWaiting(key)}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${
                waiting === key
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border text-muted hover:text-text'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      ) : null}

      {msg ? (
        <p className="rounded-md border border-border bg-surface-2 px-3 py-2 text-sm">
          {msg}
        </p>
      ) : null}

      {tab === 'assign' ? (
        <div className="rounded-lg border border-border bg-surface p-4">
          <h3 className="font-semibold">Bulk assign</h3>
          <p className="mt-1 text-sm text-muted">
            Select cases, set one due date, assign. Still uses assign_homework
            per case — no auto-visibility.
          </p>
          {!traineeFilter ? (
            <p className="mt-2 text-sm text-attention">
              Pick a trainee above to assign (keeps batches per person).
            </p>
          ) : (
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <label className="text-sm">
                Due date
                <input
                  type="date"
                  className="mt-1 block rounded-md border border-border bg-bg px-3 py-2"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                />
              </label>
              <label className="min-w-[16rem] flex-1 text-sm">
                Instructions
                <input
                  className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2"
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                />
              </label>
              <Button variant="secondary" onClick={selectNext5}>
                Select next 5
              </Button>
              <Button
                disabled={selected.size === 0 || bulkAssign.isPending}
                onClick={() => bulkAssign.mutate()}
              >
                {bulkAssign.isPending
                  ? 'Assigning…'
                  : `Assign selected (${selected.size})`}
              </Button>
            </div>
          )}
        </div>
      ) : null}

      {queueQ.isLoading ? (
        <SkeletonRows count={4} />
      ) : rows.length === 0 ? (
        <EmptyState
          title={
            tab === 'needs_you'
              ? 'Nothing needs you'
              : tab === 'assign'
                ? 'Nothing to assign'
                : 'No cases here'
          }
          description={
            tab === 'needs_you'
              ? 'When a trainee submits a package, it shows up here with Received and Last checked.'
              : undefined
          }
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((c) => (
            <QueueRow
              key={c.id}
              caseRow={c}
              tab={tab}
              selectable={tab === 'assign' && !!traineeFilter}
              checked={selected.has(c.id)}
              onToggle={() => toggle(c.id)}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function QueueRow({
  caseRow: c,
  tab,
  selectable,
  checked,
  onToggle,
}: {
  caseRow: CaseRow
  tab: Tab
  selectable: boolean
  checked: boolean
  onToggle: () => void
}) {
  const unchecked =
    tab === 'needs_you' &&
    isUnchecked(c.received_at, c.trainer_last_opened_at)

  return (
    <li
      className={`flex flex-wrap items-center gap-3 rounded-lg border bg-surface px-4 py-3 ${
        unchecked ? 'border-attention/50' : 'border-border'
      }`}
    >
      {selectable ? (
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="h-4 w-4"
          aria-label={`Select ${caseLabel(c)}`}
        />
      ) : null}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-2">
          <Link
            to={`/trainer/cases/${c.id}`}
            className="font-medium text-primary hover:underline"
          >
            {c.trainee_name ? `${c.trainee_name} · ` : ''}
            {caseLabel(c)}
          </Link>
          <StatusBadge status={c.status} />
          {unchecked ? (
            <span className="text-xs font-medium text-attention">Unchecked</span>
          ) : null}
        </div>
        <p className="mt-0.5 text-sm text-muted">
          {tab === 'needs_you'
            ? `Waiting ${formatWaitingAge(c.received_at)}`
            : nextStep(c.status, 'trainer')}
        </p>
        {tab === 'needs_you' ? (
          <p className="mt-1 text-xs text-muted">
            Received {formatShortDateTime(c.received_at)}
            {' · '}
            Last checked{' '}
            {c.trainer_last_opened_at
              ? formatShortDateTime(c.trainer_last_opened_at)
              : 'Never'}
          </p>
        ) : (
          <p className="mt-1 text-xs text-muted">
            {c.due_date ? `Due ${c.due_date}` : 'No due date'}
            {c.released_on ? ` · Suggested ${c.released_on}` : ''}
          </p>
        )}
      </div>
      <Link
        to={`/trainer/cases/${c.id}`}
        className="text-sm font-medium text-primary hover:underline"
      >
        Open
      </Link>
    </li>
  )
}
