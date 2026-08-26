import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getScreenshotSignedUrl } from '@/lib/api'
import { SECTION_LABELS, THREAD_STATUS_LABELS } from '@/lib/domain/revisions'
import type { CorrectionThread, Screenshot } from '@/lib/types'
import { Button } from './Button'
import { PasteCommentBox } from './PasteCommentBox'

/**
 * Shared open/resolved correction-thread list — trainer and trainee both
 * use this. Trainers can attach more screenshots to an open thread the same
 * way Streamlit's popover "Screenshots" control works.
 */
export function CorrectionThreadList({
  threads,
  onResolve,
  resolving,
  onAttachScreenshots,
  attaching,
  attachLabel = 'Save screenshots',
}: {
  threads: CorrectionThread[]
  onResolve?: (threadId: string) => void
  resolving?: boolean
  onAttachScreenshots?: (threadId: string, images: File[]) => Promise<void> | void
  attaching?: boolean
  /** Button label when attaching (trainer one-shot: "Send update"). */
  attachLabel?: string
}) {
  const open = threads.filter((t) => t.status !== 'resolved')
  const resolved = threads.filter((t) => t.status === 'resolved')

  if (threads.length === 0) {
    return <p className="mt-2 text-sm text-muted">No corrections on this case.</p>
  }

  return (
    <div className="mt-3 space-y-4">
      <p className="text-sm font-medium text-text">
        {open.length === 0
          ? 'All corrections resolved'
          : `${open.length} open correction${open.length === 1 ? '' : 's'}`}
      </p>

      {open.length > 0 ? (
        <ol className="space-y-2">
          {open.map((t, i) => (
            <li key={t.id}>
              <ThreadCard
                thread={t}
                index={i + 1}
                onResolve={onResolve}
                resolving={resolving}
                onAttachScreenshots={onAttachScreenshots}
                attaching={attaching}
                attachLabel={attachLabel}
              />
            </li>
          ))}
        </ol>
      ) : null}

      {resolved.length > 0 ? (
        <details className="rounded-md border border-border">
          <summary className="cursor-pointer select-none px-3 py-2 text-sm text-muted">
            {resolved.length} resolved
          </summary>
          <ul className="space-y-2 border-t border-border p-3">
            {resolved.map((t) => (
              <li key={t.id}>
                <ThreadCard thread={t} muted />
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  )
}

function ThreadCard({
  thread,
  index,
  muted,
  onResolve,
  resolving,
  onAttachScreenshots,
  attaching,
  attachLabel = 'Save screenshots',
}: {
  thread: CorrectionThread
  index?: number
  muted?: boolean
  onResolve?: (threadId: string) => void
  resolving?: boolean
  onAttachScreenshots?: (threadId: string, images: File[]) => Promise<void> | void
  attaching?: boolean
  attachLabel?: string
}) {
  const [showAttach, setShowAttach] = useState(false)
  const [note, setNote] = useState('')
  const [images, setImages] = useState<File[]>([])
  const [localMsg, setLocalMsg] = useState<string | null>(null)

  const events = thread.correction_events ?? []
  const withBody = events.filter((e) => e.body && e.body.trim())
  const stillOpenCount = events.filter(
    (e) => e.event_type === 'still_open' && !(e.body && e.body.trim()),
  ).length

  async function saveScreenshots() {
    if (!onAttachScreenshots || images.length === 0) {
      setLocalMsg('Paste or upload a screenshot first.')
      return
    }
    setLocalMsg(null)
    await onAttachScreenshots(thread.id, images)
    setImages([])
    setNote('')
    setShowAttach(false)
  }

  return (
    <div
      className={`fade-in rounded-md border border-l-4 bg-bg p-3 text-sm transition-colors ${
        muted
          ? 'border-border border-l-border opacity-70'
          : 'border-border border-l-attention'
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium text-text">
          {index ? <span className="text-muted">#{index} · </span> : null}
          {SECTION_LABELS[thread.section] ?? thread.section}
          <span className="ml-2 text-xs font-normal text-muted">
            {THREAD_STATUS_LABELS[thread.status] ?? thread.status}
          </span>
        </p>
        <div className="flex flex-wrap gap-1">
          {onAttachScreenshots && thread.status !== 'resolved' ? (
            <Button
              variant="ghost"
              onClick={() => setShowAttach((v) => !v)}
            >
              {showAttach ? 'Cancel' : 'Screenshots'}
            </Button>
          ) : null}
          {onResolve && thread.status !== 'resolved' ? (
            <Button
              variant="ghost"
              disabled={resolving}
              onClick={() => onResolve(thread.id)}
            >
              Resolve
            </Button>
          ) : null}
        </div>
      </div>

      {withBody.map((ev) => (
        <p key={ev.id} className="mt-1 text-muted">
          {ev.body}
        </p>
      ))}

      {stillOpenCount > 0 ? (
        <p className="mt-1 text-xs text-attention">
          Still open after {stillOpenCount} revision
          {stillOpenCount === 1 ? '' : 's'}
        </p>
      ) : null}

      <ThreadScreenshots shots={thread.correction_thread_screenshots ?? []} />

      {showAttach ? (
        <div className="mt-3 space-y-2">
          <PasteCommentBox
            value={note}
            onChange={setNote}
            images={images}
            onImagesChange={setImages}
            placeholder="Paste screenshots here (Ctrl+V / Cmd+V)"
            rows={3}
            disabled={attaching}
            footer={
              <Button
                disabled={attaching || images.length === 0}
                onClick={() => void saveScreenshots()}
              >
                {attaching ? 'Sending…' : attachLabel}
              </Button>
            }
          />
          {localMsg ? (
            <p className="text-xs text-attention">{localMsg}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

/** Signed-URL thumbnails for a thread's pasted/uploaded screenshots — the
 * case-files bucket is private, so every view goes through a short-lived
 * signed URL rather than a public one (same as Streamlit's "Zoom" link). */
function ThreadScreenshots({ shots }: { shots: Screenshot[] }) {
  const urlsQ = useQuery({
    queryKey: ['screenshot-urls', shots.map((s) => s.storage_path)],
    queryFn: () =>
      Promise.all(shots.map((s) => getScreenshotSignedUrl(s.storage_path))),
    enabled: shots.length > 0,
    staleTime: 5 * 60 * 1000,
  })

  if (shots.length === 0) return null

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {shots.map((shot, i) => {
        const url = urlsQ.data?.[i]
        return (
          <a
            key={shot.id}
            href={url ?? undefined}
            target="_blank"
            rel="noreferrer"
            title={shot.original_filename}
            className={`block h-20 w-28 overflow-hidden rounded-md border border-border bg-surface-2 ${
              url ? '' : 'pointer-events-none'
            }`}
          >
            {url ? (
              <img
                src={url}
                alt={shot.original_filename}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-muted">
                Loading…
              </div>
            )}
          </a>
        )
      })}
    </div>
  )
}
