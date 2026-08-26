import { describe, expect, it } from 'vitest'
import {
  daysSince,
  formatWaitingAge,
  isUnchecked,
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
