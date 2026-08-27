import { describe, expect, it } from 'vitest'
import {
  compareTraineeUrgency,
  daysSince,
  formatWaitingAge,
  isTraineeActionable,
  isUnchecked,
  sortTraineeActionable,
  traineeCtaTitle,
} from './ownership'

describe('queue date helpers', () => {
  it('daysSince floors whole days', () => {
    const now = new Date('2026-08-26T12:00:00Z')
    expect(daysSince('2026-08-26T08:00:00Z', now)).toBe(0)
    expect(daysSince('2026-08-24T12:00:00Z', now)).toBe(2)
    expect(daysSince(null, now)).toBeNull()
  })

  it('formatWaitingAge', () => {
    expect(formatWaitingAge(null)).toBe('Unknown')
    const now = new Date()
    expect(formatWaitingAge(now.toISOString())).toBe('<1d')
  })

  it('isUnchecked when never opened or opened before received', () => {
    expect(isUnchecked('2026-08-26T10:00:00Z', null)).toBe(true)
    expect(
      isUnchecked('2026-08-26T10:00:00Z', '2026-08-26T09:00:00Z'),
    ).toBe(true)
    expect(
      isUnchecked('2026-08-26T10:00:00Z', '2026-08-26T11:00:00Z'),
    ).toBe(false)
    expect(isUnchecked(null, '2026-08-26T11:00:00Z')).toBe(false)
  })
})

describe('trainee actionable queue', () => {
  it('includes owned statuses and corrections_sent with open threads', () => {
    expect(isTraineeActionable('assigned')).toBe(true)
    expect(isTraineeActionable('awaiting_resubmission')).toBe(true)
    expect(isTraineeActionable('corrections_sent', 0)).toBe(false)
    expect(isTraineeActionable('corrections_sent', 2)).toBe(true)
    expect(isTraineeActionable('in_review')).toBe(false)
  })

  it('sorts fix-corrections before prepare, and overdue before later due', () => {
    const sorted = sortTraineeActionable(
      [
        { status: 'assigned', due_date: '2026-08-20', openCorrections: 0 },
        {
          status: 'awaiting_resubmission',
          due_date: '2026-08-28',
          openCorrections: 3,
        },
        { status: 'assigned', due_date: '2026-08-27', openCorrections: 0 },
      ],
      '2026-08-26',
    )
    expect(sorted[0]?.status).toBe('awaiting_resubmission')
    expect(sorted[1]?.status).toBe('assigned')
    expect(sorted[1]?.due_date).toBe('2026-08-20')
  })

  it('compareTraineeUrgency prefers more open corrections', () => {
    expect(
      compareTraineeUrgency(
        { status: 'awaiting_resubmission', openCorrections: 1 },
        { status: 'awaiting_resubmission', openCorrections: 4 },
      ),
    ).toBeGreaterThan(0)
  })

  it('traineeCtaTitle names correction count', () => {
    expect(traineeCtaTitle('awaiting_resubmission', 3)).toBe(
      'Fix 3 corrections',
    )
    expect(traineeCtaTitle('assigned', 0)).toBe('Prepare files and submit')
  })
})
