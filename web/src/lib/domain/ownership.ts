/** Port of metrics.py ownership + next-step helpers. */

import type { AppRole, AttentionState, CaseOwner, CaseStatus } from '../types'

export const TRAINEE_OWNED_STATUSES = new Set<CaseStatus>([
  'assigned',
  'submitted',
  'awaiting_resubmission',
])

export const TRAINER_OWNED_STATUSES = new Set<CaseStatus>([
  'not_started',
  'in_review',
  'corrections_sent',
])

const NEXT_STEP: Record<string, string> = {
  'not_started:trainer': 'Assign this case',
  'not_started:trainee': 'Waiting for assignment',
  'assigned:trainee': 'Prepare files and submit package',
  'assigned:trainer': 'Waiting on trainee',
  'submitted:trainee': 'Submit package for review',
  'submitted:trainer': 'Waiting on trainee',
  'awaiting_resubmission:trainee': 'Fix corrections and resubmit',
  'awaiting_resubmission:trainer': 'Waiting on trainee',
  'in_review:trainer': 'Review package',
  'in_review:trainee': 'Waiting on trainer',
  'corrections_sent:trainer': 'Continue review or wait',
  'corrections_sent:trainee': 'Read feedback',
  'approved:trainer': 'Done',
  'approved:trainee': 'Done',
}

export const STATUS_LABELS: Record<CaseStatus, string> = {
  not_started: 'Needs assignment',
  assigned: 'Assigned',
  submitted: 'Ready to submit',
  in_review: 'In review',
  corrections_sent: 'Corrections sent',
  awaiting_resubmission: 'Awaiting resubmission',
  approved: 'Approved',
  blocked: 'Blocked',
}

export function caseOwner(status: CaseStatus | string): CaseOwner {
  if (TRAINEE_OWNED_STATUSES.has(status as CaseStatus)) return 'trainee'
  if (TRAINER_OWNED_STATUSES.has(status as CaseStatus)) return 'trainer'
  return 'none'
}

export function nextStep(status: CaseStatus | string, role: AppRole): string {
  return NEXT_STEP[`${status}:${role}`] ?? 'No action needed'
}

export function ownedByStatuses(role: AppRole): Set<CaseStatus> {
  return role === 'trainer' ? TRAINER_OWNED_STATUSES : TRAINEE_OWNED_STATUSES
}

export function attentionState(status: CaseStatus | string): AttentionState {
  if (status === 'approved') return 'approved'
  if (status === 'not_started') return 'assigned'
  if (TRAINEE_OWNED_STATUSES.has(status as CaseStatus)) return 'with_trainee'
  if (status === 'in_review' || status === 'corrections_sent') {
    return 'needs_trainer'
  }
  return 'with_trainee'
}

export function ownerLabel(owner: CaseOwner): string {
  if (owner === 'trainee') return 'Trainee'
  if (owner === 'trainer') return 'Trainer'
  return 'None'
}

export function formatDue(due: string | null | undefined): string {
  if (!due) return 'No due date'
  return due
}

export function formatShortDateTime(
  iso: string | null | undefined,
): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Whole days since `iso` (UTC date math). Null if missing. */
export function daysSince(iso: string | null | undefined, now = new Date()): number | null {
  if (!iso) return null
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return null
  const ms = now.getTime() - then.getTime()
  return Math.max(0, Math.floor(ms / (24 * 60 * 60 * 1000)))
}

export function formatWaitingAge(iso: string | null | undefined): string {
  const days = daysSince(iso)
  if (days === null) return 'Unknown'
  if (days === 0) return '<1d'
  return `${days}d`
}

/** True when trainer never opened, or opened before the latest package Received. */
export function isUnchecked(
  receivedAt: string | null | undefined,
  lastOpenedAt: string | null | undefined,
): boolean {
  if (!lastOpenedAt) return true
  if (!receivedAt) return false
  return lastOpenedAt < receivedAt
}

export function isOverdue(
  status: CaseStatus | string,
  due: string | null | undefined,
  today = new Date().toISOString().slice(0, 10),
): boolean {
  if (!due || status === 'approved' || status === 'blocked') return false
  return due < today
}

/**
 * Cases the trainee should act on in their dashboard queue.
 * Includes legacy `corrections_sent` when open threads exist (read feedback)
 * even though that status is trainer-owned for file edits.
 */
export function isTraineeActionable(
  status: CaseStatus | string,
  openCorrectionCount = 0,
): boolean {
  if (TRAINEE_OWNED_STATUSES.has(status as CaseStatus)) return true
  return status === 'corrections_sent' && openCorrectionCount > 0
}

/** Journey / list tone from the trainee's point of view. */
export function traineeAttentionState(
  status: CaseStatus | string,
): AttentionState {
  if (status === 'approved') return 'approved'
  if (status === 'not_started') return 'assigned'
  if (
    TRAINEE_OWNED_STATUSES.has(status as CaseStatus) ||
    status === 'corrections_sent'
  ) {
    return 'with_trainee'
  }
  if (status === 'in_review') return 'needs_trainer'
  return 'with_trainee'
}

const SHORT_TRAINEE_STEP: Record<string, string> = {
  'Prepare files and submit package': 'Prepare files',
  'Submit package for review': 'Submit package',
  'Fix corrections and resubmit': 'Fix corrections',
  'Replace requested files': 'Fix corrections',
  'Read feedback': 'Read feedback',
  'Waiting on trainer': 'With trainer',
}

export function shortTraineeStep(status: CaseStatus | string): string {
  const full = nextStep(status, 'trainee')
  return SHORT_TRAINEE_STEP[full] ?? full
}

export function traineeCtaTitle(
  status: CaseStatus | string,
  openCorrectionCount = 0,
): string {
  if (
    status === 'awaiting_resubmission' ||
    (status === 'corrections_sent' && openCorrectionCount > 0)
  ) {
    if (openCorrectionCount > 0) {
      return `Fix ${openCorrectionCount} correction${openCorrectionCount === 1 ? '' : 's'}`
    }
    return 'Fix corrections and resubmit'
  }
  if (status === 'assigned') return 'Prepare files and submit'
  if (status === 'submitted') return 'Submit package for review'
  return shortTraineeStep(status)
}

type UrgencyRow = {
  status: CaseStatus | string
  due_date?: string | null
  openCorrections?: number
}

/** Sort key: fix-corrections first, then overdue, then sooner due, then status. */
export function compareTraineeUrgency(
  a: UrgencyRow,
  b: UrgencyRow,
  today = new Date().toISOString().slice(0, 10),
): number {
  const bucket = (row: UrgencyRow) => {
    const opens = row.openCorrections ?? 0
    if (
      row.status === 'awaiting_resubmission' ||
      (row.status === 'corrections_sent' && opens > 0)
    ) {
      return 0
    }
    if (isOverdue(row.status, row.due_date, today)) return 1
    if (row.status === 'assigned' || row.status === 'submitted') return 2
    return 3
  }
  const d = bucket(a) - bucket(b)
  if (d !== 0) return d
  const opens = (b.openCorrections ?? 0) - (a.openCorrections ?? 0)
  if (opens !== 0) return opens
  const da = a.due_date ?? '9999-99-99'
  const db = b.due_date ?? '9999-99-99'
  return da.localeCompare(db)
}

export function sortTraineeActionable<T extends UrgencyRow>(
  rows: T[],
  today = new Date().toISOString().slice(0, 10),
): T[] {
  return [...rows].sort((a, b) => compareTraineeUrgency(a, b, today))
}
