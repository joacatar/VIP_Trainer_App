import { describe, expect, it } from 'vitest'
import {
  flattenCorrections,
  groupRepeated,
  resolutionStats,
  sectionBreakdown,
  traineeBreakdown,
} from '@/lib/domain/correctionAnalytics'
import type { RaisedCorrectionRow } from '@/lib/types'

function row(opts: {
  id: string
  body: string | null
  section?: string
  threadId?: string
  threadStatus?: string
  caseId?: string
  traineeId?: string
  traineeName?: string
  createdAt?: string
}): RaisedCorrectionRow {
  return {
    id: opts.id,
    body: opts.body,
    created_at: opts.createdAt ?? '2026-08-01T00:00:00Z',
    corrections_threads: {
      id: opts.threadId ?? `thread-${opts.id}`,
      section: opts.section ?? 'humeral_landmark',
      status: opts.threadStatus ?? 'resolved',
      case_id: opts.caseId ?? 'case-1',
      created_at: '2026-08-01T00:00:00Z',
      resolved_at: null,
      cases: {
        id: opts.caseId ?? 'case-1',
        trainee_id: opts.traineeId ?? 'trainee-1',
        phase_no: 2,
        set_no: 1,
        case_no: 4,
        catalog_label: 'L04',
        trainees: { full_name: opts.traineeName ?? 'AARON FONG' },
      },
    },
  }
}

describe('flattenCorrections', () => {
  it('drops raised events with no body text', () => {
    const rows = [
      row({ id: '1', body: 'Implant version changed' }),
      row({ id: '2', body: null }),
      row({ id: '3', body: '   ' }),
    ]
    expect(flattenCorrections(rows)).toHaveLength(1)
  })

  it('carries the case label and trainee name through', () => {
    const [flat] = flattenCorrections([row({ id: '1', body: 'x' })])
    expect(flat.caseLabel).toBe('Live case L04')
    expect(flat.traineeName).toBe('AARON FONG')
    expect(flat.sectionLabel).toBe('Humeral landmark')
  })
})

describe('groupRepeated', () => {
  it('treats case/whitespace variants as the same correction', () => {
    const rows = [
      row({ id: '1', body: 'Implant version changed' }),
      row({ id: '2', body: '  implant   version changed ' }),
      row({ id: '3', body: 'Implant version changed' }),
    ]
    const groups = groupRepeated(flattenCorrections(rows), 2)
    expect(groups).toHaveLength(1)
    expect(groups[0].count).toBe(3)
  })

  it('filters out corrections below minCount', () => {
    const rows = [
      row({ id: '1', body: 'One-off note' }),
      row({ id: '2', body: 'Implant version changed' }),
      row({ id: '3', body: 'Implant version changed' }),
    ]
    const groups = groupRepeated(flattenCorrections(rows), 2)
    expect(groups.map((g) => g.body)).toEqual(['Implant version changed'])
  })

  it('sorts by count descending and tracks distinct trainees', () => {
    const rows = [
      row({ id: '1', body: 'A', traineeId: 't1', traineeName: 'Aaron' }),
      row({ id: '2', body: 'A', traineeId: 't1', traineeName: 'Aaron' }),
      row({ id: '3', body: 'B', traineeId: 't1', traineeName: 'Aaron' }),
      row({ id: '4', body: 'B', traineeId: 't2', traineeName: 'Max' }),
      row({ id: '5', body: 'B', traineeId: 't2', traineeName: 'Max' }),
      row({ id: '6', body: 'B', traineeId: 't2', traineeName: 'Max' }),
    ]
    const groups = groupRepeated(flattenCorrections(rows), 2)
    expect(groups[0].body).toBe('B')
    expect(groups[0].count).toBe(4)
    expect(groups[0].traineeNames.sort()).toEqual(['Aaron', 'Max'])
    expect(groups[1].body).toBe('A')
  })
})

describe('sectionBreakdown / traineeBreakdown', () => {
  const rows = [
    row({ id: '1', body: 'A', section: 'scapula', traineeId: 't1', traineeName: 'Aaron' }),
    row({ id: '2', body: 'B', section: 'scapula', traineeId: 't2', traineeName: 'Max' }),
    row({ id: '3', body: 'C', section: 'scan', traineeId: 't1', traineeName: 'Aaron' }),
  ]
  const flat = flattenCorrections(rows)

  it('counts by section, most frequent first', () => {
    expect(sectionBreakdown(flat)).toEqual([
      { key: 'scapula', label: 'Scapula', count: 2 },
      { key: 'scan', label: 'Scan', count: 1 },
    ])
  })

  it('counts by trainee, most frequent first', () => {
    expect(traineeBreakdown(flat)).toEqual([
      { key: 't1', label: 'Aaron', count: 2 },
      { key: 't2', label: 'Max', count: 1 },
    ])
  })
})

describe('resolutionStats', () => {
  it('counts distinct threads, not raised events', () => {
    const rows = [
      row({ id: '1', body: 'A', threadId: 'th1', threadStatus: 'resolved' }),
      row({ id: '2', body: 'still open after revision', threadId: 'th1', threadStatus: 'resolved' }),
      row({ id: '3', body: 'B', threadId: 'th2', threadStatus: 'open' }),
    ]
    const stats = resolutionStats(flattenCorrections(rows))
    expect(stats.totalThreads).toBe(2)
    expect(stats.resolvedThreads).toBe(1)
    expect(stats.resolutionRate).toBe(0.5)
  })
})
