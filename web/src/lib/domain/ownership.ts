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
  'awaiting_resubmission:trainee': 'Replace requested files',
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

export function isOverdue(
  status: CaseStatus | string,
  due: string | null | undefined,
  today = new Date().toISOString().slice(0, 10),
): boolean {
  if (!due || status === 'approved' || status === 'blocked') return false
  return due < today
}
