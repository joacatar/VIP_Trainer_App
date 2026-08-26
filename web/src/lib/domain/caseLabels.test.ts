import { describe, expect, it } from 'vitest'
import {
  caseCatalogLabel,
  caseLabel,
  caseOrderNumber,
  casePhaseNo,
  caseTitle,
} from '@/lib/domain/caseLabels'
import {
  attentionState,
  caseOwner,
  nextStep,
  TRAINEE_OWNED_STATUSES,
  TRAINER_OWNED_STATUSES,
} from '@/lib/domain/ownership'

describe('case ownership', () => {
  it('gives not_started to the trainer, not the trainee', () => {
    expect(caseOwner('not_started')).toBe('trainer')
    expect(TRAINER_OWNED_STATUSES.has('not_started')).toBe(true)
    expect(TRAINEE_OWNED_STATUSES.has('not_started')).toBe(false)
    expect(nextStep('not_started', 'trainer')).toBe('Assign this case')
    expect(nextStep('not_started', 'trainee')).toBe('Waiting for assignment')
  })

  it('maps attention lanes without treating not_started as with_trainee', () => {
    expect(attentionState('not_started')).toBe('assigned')
    expect(attentionState('assigned')).toBe('with_trainee')
    expect(attentionState('in_review')).toBe('needs_trainer')
    expect(attentionState('approved')).toBe('approved')
  })
})

describe('case labels', () => {
  it('never falls back to phase-1 VIP numbers for phase-2 rows', () => {
    const phase2 = {
      phase_no: 2,
      set_no: 1,
      case_no: 1,
      catalog_label: 'L01',
      order_number: null,
    }
    expect(casePhaseNo(phase2)).toBe(2)
    expect(caseOrderNumber(phase2)).toBeNull()
    expect(caseTitle(phase2)).toBe('Live case L01')
    expect(caseLabel(phase2)).toBe('Live case L01')
  })

  it('uses phase-1 fallback map only for phase 1', () => {
    const phase1 = {
      phase_no: 1,
      set_no: 1,
      case_no: 1,
      catalog_label: null,
      order_number: null,
    }
    expect(caseCatalogLabel(phase1)).toBe('1A')
    expect(caseOrderNumber(phase1)).toBe('12-26-02-0002')
    expect(caseTitle(phase1)).toContain('Set 1')
  })

  it('prefers stored order_number when present on phase 2', () => {
    expect(
      caseOrderNumber({
        phase_no: 2,
        set_no: 1,
        case_no: 3,
        order_number: '12-26-99-0001',
      }),
    ).toBe('12-26-99-0001')
  })
})
