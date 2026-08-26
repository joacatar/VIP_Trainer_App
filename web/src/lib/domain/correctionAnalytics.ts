/** Turns raw `correction_events` rows into the repeat-correction and
 * per-section/per-trainee breakdowns shown on the trainer's Analytics page
 * and the trainee's My corrections page. Pure and Supabase-free so it stays
 * unit-testable — see correctionAnalytics.test.ts. */

import { caseLabel } from './caseLabels'
import { SECTION_LABELS } from './revisions'
import type { RaisedCorrectionRow } from '../types'

export interface FlatCorrection {
  id: string
  body: string
  createdAt: string
  section: string
  sectionLabel: string
  threadId: string
  threadStatus: string
  caseId: string
  caseLabel: string
  traineeId: string
  traineeName: string
}

/** Blank-body raised events happen (a trainer can raise a thread and add
 * the actual note as a later event) — they carry no text to analyze, so
 * they're dropped here rather than showing up as a nameless correction. */
export function flattenCorrections(rows: RaisedCorrectionRow[]): FlatCorrection[] {
  const out: FlatCorrection[] = []
  for (const r of rows) {
    const thread = r.corrections_threads
    const c = thread?.cases
    const body = r.body?.trim()
    if (!thread || !c || !body) continue
    out.push({
      id: r.id,
      body,
      createdAt: r.created_at,
      section: thread.section,
      sectionLabel: SECTION_LABELS[thread.section] ?? thread.section,
      threadId: thread.id,
      threadStatus: thread.status,
      caseId: c.id,
      caseLabel: caseLabel(c),
      traineeId: c.trainee_id,
      traineeName: c.trainees?.full_name ?? 'Unknown',
    })
  }
  return out
}

/** Groups near-duplicate text (case, extra whitespace) as the same
 * correction — catches "Edit button." vs "edit button." without pulling in
 * a fuzzy-match library for what's still exact-text grouping underneath. */
function normalizeBody(body: string): string {
  return body.toLowerCase().replace(/\s+/g, ' ').trim()
}

export interface RepeatedGroup {
  key: string
  section: string
  sectionLabel: string
  /** Display text — the first-seen occurrence's original casing. */
  body: string
  count: number
  traineeNames: string[]
  occurrences: FlatCorrection[]
  lastSeen: string
}

/** Same (section, normalized body) raised `minCount` times or more, most
 * frequent first. This is the "what keeps repeating" view — the backlog
 * task from the audit ("audit which corrections actually repeat, from real
 * usage") and the direct answer to whether a checklist chip earns its
 * place or a case-workspace pattern needs fixing at the source instead of
 * being corrected by hand every time. */
export function groupRepeated(
  items: FlatCorrection[],
  minCount = 2,
): RepeatedGroup[] {
  const map = new Map<string, RepeatedGroup>()
  for (const item of items) {
    const key = `${item.section}::${normalizeBody(item.body)}`
    let g = map.get(key)
    if (!g) {
      g = {
        key,
        section: item.section,
        sectionLabel: item.sectionLabel,
        body: item.body,
        count: 0,
        traineeNames: [],
        occurrences: [],
        lastSeen: item.createdAt,
      }
      map.set(key, g)
    }
    g.count += 1
    g.occurrences.push(item)
    if (!g.traineeNames.includes(item.traineeName)) g.traineeNames.push(item.traineeName)
    if (item.createdAt > g.lastSeen) g.lastSeen = item.createdAt
  }
  return [...map.values()]
    .filter((g) => g.count >= minCount)
    .sort((a, b) => b.count - a.count || b.lastSeen.localeCompare(a.lastSeen))
}

export interface CountBucket {
  key: string
  label: string
  count: number
}

export function sectionBreakdown(items: FlatCorrection[]): CountBucket[] {
  const map = new Map<string, number>()
  for (const item of items) map.set(item.section, (map.get(item.section) ?? 0) + 1)
  return [...map.entries()]
    .map(([section, count]) => ({
      key: section,
      label: SECTION_LABELS[section] ?? section,
      count,
    }))
    .sort((a, b) => b.count - a.count)
}

export function traineeBreakdown(items: FlatCorrection[]): CountBucket[] {
  const map = new Map<string, CountBucket>()
  for (const item of items) {
    const existing = map.get(item.traineeId)
    if (existing) existing.count += 1
    else
      map.set(item.traineeId, {
        key: item.traineeId,
        label: item.traineeName,
        count: 1,
      })
  }
  return [...map.values()].sort((a, b) => b.count - a.count)
}

/** How many top-ranked repeated corrections get the "focus area" treatment
 * on Analytics and My corrections — a trainer commitment to build real
 * resources for the worst offenders, not just relabel the checklist chip.
 * Static and hardcoded on purpose (trainer's call): once the current ones
 * are actually addressed, bump this rather than making it auto-scale. */
export const FOCUS_AREA_COUNT = 2

/** The trainer's standard action plan for a focus area — same steps every
 * time. Shown on the trainer's Analytics page only; My corrections shows
 * trainees a short announcement instead, not the internal plan. Static on
 * purpose — no table, no per-item state, just the trainer's stated intent. */
export const FOCUS_AREA_PLAN = [
  'Collect work-instruction material',
  'Generate infographics',
  'Review edge cases',
  'Build a practice exam',
]

/** Distinct thread count and how many of those threads are resolved —
 * "raised" events can outnumber threads (a thread gets `still_open` stamps
 * on every revision it survives), so this is not just `items.length`. */
export function resolutionStats(items: FlatCorrection[]): {
  totalThreads: number
  resolvedThreads: number
  resolutionRate: number
} {
  const threads = new Map<string, string>()
  for (const item of items) threads.set(item.threadId, item.threadStatus)
  const totalThreads = threads.size
  const resolvedThreads = [...threads.values()].filter((s) => s === 'resolved')
    .length
  return {
    totalThreads,
    resolvedThreads,
    resolutionRate: totalThreads === 0 ? 0 : resolvedThreads / totalThreads,
  }
}
