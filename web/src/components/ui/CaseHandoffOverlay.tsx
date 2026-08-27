import { useEffect, useState } from 'react'
import { Button } from './Button'

export type CaseHandoffState = {
  handoff: true
  action: 'sent' | 'updated' | 'approved'
  fromLabel: string
  fromTrainee?: string | null
}

const ACTION_COPY: Record<CaseHandoffState['action'], string> = {
  sent: 'after sending a correction',
  updated: 'after sending an update',
  approved: 'after approving',
}

/**
 * Full-screen handoff when the trainer lands on the next Needs you case.
 * Requires an explicit Continue so the case change is hard to miss.
 */
export function CaseHandoffOverlay({
  handoff,
  nowLabel,
  nowTrainee,
  onContinue,
}: {
  handoff: CaseHandoffState
  nowLabel: string
  nowTrainee?: string | null
  onContinue: () => void
}) {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const t = window.setTimeout(() => setReady(true), 80)
    return () => window.clearTimeout(t)
  }, [])

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-sidebar/90 p-6 backdrop-blur-sm transition-opacity duration-200 ${
        ready ? 'opacity-100' : 'opacity-0'
      }`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="case-handoff-title"
    >
      <div
        className={`w-full max-w-md rounded-2xl border border-white/15 bg-surface p-6 shadow-2xl transition duration-300 ${
          ready ? 'translate-y-0 scale-100 opacity-100' : 'translate-y-3 scale-95 opacity-0'
        }`}
      >
        <p className="text-xs font-semibold uppercase tracking-wider text-primary">
          Next case
        </p>
        <h2 id="case-handoff-title" className="mt-2 text-2xl font-semibold text-text">
          Now reviewing {nowLabel}
        </h2>
        {nowTrainee ? (
          <p className="mt-1 text-sm text-muted">{nowTrainee}</p>
        ) : null}
        <p className="mt-4 rounded-md border border-border bg-surface-2 px-3 py-2 text-sm text-text">
          You left <strong>{handoff.fromLabel}</strong>{' '}
          {ACTION_COPY[handoff.action]}.
          {handoff.fromTrainee && handoff.fromTrainee !== nowTrainee
            ? ` Previous trainee: ${handoff.fromTrainee}.`
            : null}
        </p>
        <p className="mt-3 text-sm text-muted">
          Confirm the case label above before you send anything else.
        </p>
        <div className="mt-5 flex justify-end">
          <Button onClick={onContinue}>Got it — continue</Button>
        </div>
      </div>
    </div>
  )
}
