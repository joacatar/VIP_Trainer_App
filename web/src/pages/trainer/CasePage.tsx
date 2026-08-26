import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ActionBar } from '@/components/ui/ActionBar'
import { Button } from '@/components/ui/Button'
import { CaseHeader } from '@/components/ui/CaseHeader'
import { CorrectionThreadList } from '@/components/ui/CorrectionThreadList'
import { EmptyState } from '@/components/ui/EmptyState'
import { NextStepCallout } from '@/components/ui/NextStepCallout'
import { PasteCommentBox } from '@/components/ui/PasteCommentBox'
import { SkeletonRows } from '@/components/ui/Skeleton'
import { PageHeader } from '@/components/ui/PageHeader'
import { useAuth } from '@/hooks/useAuth'
import {
  answerQuestion,
  createCorrectionThread,
  createRevision,
  discardEmptyDraftRevisions,
  getCase,
  getCaseOwnerUserId,
  getTrainee,
  listCorrectionThreads,
  listQuestionsForCase,
  listRequirementsForCase,
  listRevisionsForCase,
  markOpenThreadsStillOpen,
  publishCaseReview,
  resolveThread,
  reviewFileRequirement,
  touchCaseOpened,
  uploadThreadScreenshot,
} from '@/lib/api'
import {
  FILE_KIND_LABELS,
  FILE_STATUS_LABELS,
  REVIEW_SECTIONS,
  SECTION_CHECKLISTS,
  SECTION_LABELS,
} from '@/lib/domain/revisions'
import type { CaseStatus } from '@/lib/types'

const REVIEWABLE: CaseStatus[] = ['in_review', 'corrections_sent']
const RELATED_OPTIONS = [
  { value: '', label: 'Not file-specific' },
  { value: 'pdf1', label: 'PDF 1' },
  { value: 'pdf2', label: 'PDF 2' },
  { value: 'ov', label: 'OV' },
] as const

/**
 * Trainer review — one-shot send (no draft park). Approve or send a
 * correction / screenshot update in a single action.
 */
export function TrainerCasePage() {
  const { caseId = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { user } = useAuth()
  const [section, setSection] = useState<string>(REVIEW_SECTIONS[0].key)
  const [body, setBody] = useState('')
  const [relatedFile, setRelatedFile] = useState('')
  const [pendingImages, setPendingImages] = useState<File[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [msg, setMsg] = useState<string | null>(null)
  const [msgTone, setMsgTone] = useState<'ok' | 'err'>('ok')

  const caseQ = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => getCase(caseId, { includeSource: true }),
    enabled: !!caseId,
  })
  const traineeQ = useQuery({
    queryKey: ['trainee', caseQ.data?.trainee_id],
    queryFn: () => getTrainee(caseQ.data!.trainee_id!),
    enabled: !!caseQ.data?.trainee_id,
  })
  const ownerQ = useQuery({
    queryKey: ['case-owner', caseId],
    queryFn: () => getCaseOwnerUserId(caseId),
    enabled: !!caseId,
  })
  const reqQ = useQuery({
    queryKey: ['requirements', caseId],
    queryFn: () => listRequirementsForCase(caseId),
    enabled: !!caseId,
  })
  const threadsQ = useQuery({
    queryKey: ['threads', caseId],
    queryFn: () => listCorrectionThreads(caseId),
    enabled: !!caseId,
  })
  const questionsQ = useQuery({
    queryKey: ['case-questions', caseId],
    queryFn: () => listQuestionsForCase(caseId),
    enabled: !!caseId,
  })
  const revisionsQ = useQuery({
    queryKey: ['revisions', caseId],
    queryFn: () => listRevisionsForCase(caseId),
    enabled: !!caseId,
  })

  // Stamp Last checked once per visit; discard empty orphan drafts.
  useEffect(() => {
    if (!caseId) return
    void touchCaseOpened(caseId).catch(() => {
      /* non-fatal — queue still works without stamp */
    })
    void discardEmptyDraftRevisions(caseId)
      .then(() => qc.invalidateQueries({ queryKey: ['revisions', caseId] }))
      .catch(() => {
        /* ignore — approve path still works if discard fails */
      })
  }, [caseId, qc])

  const ownerUserId =
    ownerQ.data ?? traineeQ.data?.auth_user_id ?? user?.id ?? ''

  const draftRevision = useMemo(() => {
    return (revisionsQ.data ?? []).find((r) => r.status === 'draft') ?? null
  }, [revisionsQ.data])
  const draftRevisionId = (draftRevision?.id as string | undefined) ?? null

  const openThreads = useMemo(
    () => (threadsQ.data ?? []).filter((t) => t.status !== 'resolved'),
    [threadsQ.data],
  )
  const replacementCount = useMemo(
    () =>
      (reqQ.data ?? []).filter((r) => r.status === 'replacement_requested')
        .length,
    [reqQ.data],
  )

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['case', caseId] })
    void qc.invalidateQueries({ queryKey: ['requirements', caseId] })
    void qc.invalidateQueries({ queryKey: ['threads', caseId] })
    void qc.invalidateQueries({ queryKey: ['case-questions', caseId] })
    void qc.invalidateQueries({ queryKey: ['revisions', caseId] })
    void qc.invalidateQueries({ queryKey: ['trainer-queue'] })
    void qc.invalidateQueries({ queryKey: ['trainer-cases'] })
    void qc.invalidateQueries({ queryKey: ['progress'] })
    void qc.invalidateQueries({ queryKey: ['screenshot-urls'] })
  }

  const flash = (text: string, tone: 'ok' | 'err' = 'ok') => {
    setMsg(text)
    setMsgTone(tone)
  }

  async function uploadPending(threadId: string, images: File[]) {
    for (const file of images) {
      await uploadThreadScreenshot({
        threadId,
        caseId,
        ownerUserId,
        uploadedBy: user?.id ?? '',
        file,
      })
    }
  }

  async function ensureDraftRevisionId(): Promise<string> {
    if (draftRevisionId) return draftRevisionId
    await discardEmptyDraftRevisions(caseId)
    return createRevision(caseId)
  }

  async function publishAndNotify(revisionId: string) {
    await publishCaseReview({
      caseId,
      revisionId,
      approvePackage: false,
    })
    await markOpenThreadsStillOpen(caseId, revisionId)
  }

  const sendCorrection = useMutation({
    mutationFn: async () => {
      if (!body.trim() && pendingImages.length === 0) {
        throw new Error('Write a correction or paste a screenshot first.')
      }
      const revisionId = await ensureDraftRevisionId()
      const threadId = await createCorrectionThread({
        caseId,
        section,
        body: body.trim() || 'See attached screenshot(s).',
        revisionId,
        relatedFile: relatedFile || null,
      })
      if (pendingImages.length > 0) {
        await uploadPending(threadId, pendingImages)
      }
      await publishAndNotify(revisionId)
      return threadId
    },
    onSuccess: () => {
      setBody('')
      setPendingImages([])
      flash('Sent to trainee.')
      invalidate()
      navigate('/trainer/cases?tab=needs_you')
    },
    onError: (e: Error) => flash(e.message, 'err'),
  })

  const sendThreadUpdate = useMutation({
    mutationFn: async ({
      threadId,
      images,
    }: {
      threadId: string
      images: File[]
    }) => {
      if (images.length === 0) {
        throw new Error('Paste or upload a screenshot first.')
      }
      const revisionId = await ensureDraftRevisionId()
      await uploadPending(threadId, images)
      await publishAndNotify(revisionId)
      return threadId
    },
    onSuccess: () => {
      flash('Update sent to trainee.')
      invalidate()
      navigate('/trainer/cases?tab=needs_you')
    },
    onError: (e: Error) => flash(e.message, 'err'),
  })

  const sendReplacements = useMutation({
    mutationFn: async () => {
      if (replacementCount === 0) {
        throw new Error('Mark at least one file for replacement first.')
      }
      // File decisions already applied via review_file_requirement; publish
      // to move the case to awaiting_resubmission / notify path.
      await publishCaseReview({
        caseId,
        revisionId: draftRevisionId,
        approvePackage: false,
      })
      if (draftRevisionId && openThreads.length > 0) {
        await markOpenThreadsStillOpen(caseId, draftRevisionId)
      }
    },
    onSuccess: () => {
      flash('Sent — trainee must replace marked files.')
      invalidate()
      navigate('/trainer/cases?tab=needs_you')
    },
    onError: (e: Error) => flash(e.message, 'err'),
  })

  const approve = useMutation({
    mutationFn: async () => {
      await discardEmptyDraftRevisions(caseId)
      const acceptAll = (reqQ.data ?? [])
        .filter((r) =>
          ['submitted', 'under_review', 'accepted'].includes(r.status),
        )
        .map((r) => ({
          requirement_id: r.id,
          decision: 'accepted',
          note: '',
        }))
      await publishCaseReview({
        caseId,
        revisionId: null,
        fileDecisions: acceptAll,
        approvePackage: true,
      })
    },
    onSuccess: () => {
      flash('Case approved.')
      invalidate()
      navigate('/trainer/cases?tab=needs_you')
    },
    onError: (e: Error) => flash(e.message, 'err'),
  })

  const fileDecision = useMutation({
    mutationFn: (input: {
      requirementId: string
      decision: string
      note?: string
    }) => reviewFileRequirement(input),
    onSuccess: (_d, vars) => {
      flash(
        vars.decision === 'accepted'
          ? 'File accepted.'
          : 'Replacement marked — click Send replacements when ready.',
      )
      invalidate()
    },
    onError: (e: Error) => flash(e.message, 'err'),
  })

  const answer = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) =>
      answerQuestion(id, text),
    onSuccess: () => {
      flash('Answer sent.')
      invalidate()
    },
  })

  const resolve = useMutation({
    mutationFn: (threadId: string) => resolveThread(threadId, draftRevisionId),
    onSuccess: () => invalidate(),
    onError: (e: Error) => flash(e.message, 'err'),
  })

  const caseRow = caseQ.data
  if (caseQ.isLoading) return <SkeletonRows count={3} />
  if (!caseRow) {
    return <EmptyState title="Case not found" />
  }

  const canReview = REVIEWABLE.includes(caseRow.status)
  const checklists = SECTION_CHECKLISTS[section] ?? []
  const canApprove =
    canReview && openThreads.length === 0 && replacementCount === 0
  const busy =
    sendCorrection.isPending ||
    sendThreadUpdate.isPending ||
    sendReplacements.isPending ||
    approve.isPending

  return (
    <div className="space-y-6 pb-28">
      <PageHeader
        title="Review"
        description="Approve the package, or send one correction — no draft to forget."
        action={
          <Link
            to="/trainer/cases?tab=needs_you"
            className="text-sm text-primary hover:underline"
          >
            Back to Needs you
          </Link>
        }
      />

      <CaseHeader
        caseRow={caseRow}
        role="trainer"
        traineeName={traineeQ.data?.full_name}
      />

      {caseRow.source_order_number ? (
        <p className="text-sm text-muted">
          Source VIP: {caseRow.source_order_number}
        </p>
      ) : null}

      {msg ? (
        <p
          className={`rounded-md border px-3 py-2 text-sm ${
            msgTone === 'err'
              ? 'border-danger/40 bg-danger/10 text-danger'
              : 'border-success/40 bg-success/10 text-success'
          }`}
        >
          {msg}
        </p>
      ) : null}

      {!canReview ? (
        <NextStepCallout title="Not in review">
          Status is <strong>{caseRow.status}</strong>. Approve / send only work
          when the case is <strong>in review</strong> or{' '}
          <strong>corrections sent</strong>.
          {caseRow.status === 'approved'
            ? ' Already approved — cannot send back from the app.'
            : null}
        </NextStepCallout>
      ) : null}

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">Files</h3>
        <ul className="mt-3 space-y-3">
          {(reqQ.data ?? []).map((req) => (
            <li
              key={req.id}
              className="rounded-md border border-border bg-bg p-3 text-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">
                  {FILE_KIND_LABELS[req.kind] ?? req.kind}
                </p>
                <span className="text-xs text-muted">
                  {FILE_STATUS_LABELS[req.status] ?? req.status}
                </span>
              </div>
              {req.external_url ? (
                <a
                  href={req.external_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-primary hover:underline"
                >
                  Open OneDrive link
                </a>
              ) : (
                <p className="mt-1 text-muted">No link yet</p>
              )}
              {canReview ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      fileDecision.mutate({
                        requirementId: req.id,
                        decision: 'accepted',
                      })
                    }
                  >
                    Accept
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() =>
                      fileDecision.mutate({
                        requirementId: req.id,
                        decision: 'rejected',
                        note: 'Please replace this file',
                      })
                    }
                  >
                    Request replacement
                  </Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
        {canReview && replacementCount > 0 ? (
          <ActionBar>
            <Button
              disabled={busy}
              onClick={() => sendReplacements.mutate()}
            >
              {sendReplacements.isPending
                ? 'Sending…'
                : `Send replacements (${replacementCount})`}
            </Button>
          </ActionBar>
        ) : null}
      </section>

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">Send a correction</h3>
        <p className="mt-1 text-sm text-muted">
          One correction (text and/or screenshots) goes to the trainee
          immediately.
        </p>

        {!canReview ? (
          <p className="mt-3 text-sm text-muted">Disabled while not in review.</p>
        ) : (
          <>
            <div className="mt-3 flex flex-wrap gap-2">
              {REVIEW_SECTIONS.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  onClick={() => setSection(s.key)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                    section === s.key
                      ? 'bg-primary text-primary-fg'
                      : 'bg-surface-2 text-muted'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {RELATED_OPTIONS.map((opt) => (
                <button
                  key={opt.value || 'none'}
                  type="button"
                  onClick={() => setRelatedFile(opt.value)}
                  className={`rounded-md border px-2.5 py-1 text-xs ${
                    relatedFile === opt.value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {checklists.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {checklists.map((item) => (
                  <button
                    key={item}
                    type="button"
                    className="rounded-md border border-border bg-bg px-2 py-1 text-left text-xs hover:border-primary"
                    onClick={() =>
                      setBody((prev) => (prev ? `${prev}\n${item}` : item))
                    }
                  >
                    {item}
                  </button>
                ))}
              </div>
            ) : null}

            <div className="mt-3">
              <PasteCommentBox
                value={body}
                onChange={setBody}
                images={pendingImages}
                onImagesChange={setPendingImages}
                placeholder={`Correction for ${SECTION_LABELS[section]}… Paste with Ctrl+V / Cmd+V`}
                disabled={busy}
              />
            </div>
            <ActionBar>
              <Button
                disabled={
                  busy || (!body.trim() && pendingImages.length === 0)
                }
                onClick={() => sendCorrection.mutate()}
              >
                {sendCorrection.isPending ? 'Sending…' : 'Send correction'}
              </Button>
            </ActionBar>
          </>
        )}
      </section>

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">
          Open corrections ({openThreads.length})
        </h3>
        <CorrectionThreadList
          threads={threadsQ.data ?? []}
          onResolve={canReview ? (id) => resolve.mutate(id) : undefined}
          resolving={resolve.isPending}
          attaching={sendThreadUpdate.isPending}
          attachLabel="Send update"
          onAttachScreenshots={
            canReview
              ? async (threadId, images) => {
                  await sendThreadUpdate.mutateAsync({ threadId, images })
                }
              : undefined
          }
        />
      </section>

      {canReview ? (
        <section className="sticky bottom-0 z-20 -mx-6 border-t border-border bg-surface/95 px-6 py-4 shadow-[0_-8px_24px_rgba(0,0,0,0.08)] backdrop-blur">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
            <div className="text-sm">
              <p className="font-semibold">Finish</p>
              <p className="text-muted">
                {canApprove
                  ? 'No open corrections — you can approve.'
                  : openThreads.length > 0
                    ? 'Resolve open corrections before approving, or send another.'
                    : 'Clear file replacements before approving.'}
              </p>
            </div>
            <Button
              disabled={!canApprove || busy}
              onClick={() => approve.mutate()}
            >
              {approve.isPending ? 'Approving…' : 'Approve case'}
            </Button>
          </div>
        </section>
      ) : null}

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">Questions</h3>
        <ul className="mt-3 space-y-3">
          {(questionsQ.data ?? []).map((q) => (
            <li
              key={q.id}
              className="rounded-md border border-border bg-bg p-3 text-sm"
            >
              <p className="font-medium">{q.body}</p>
              {q.answer_body ? (
                <p className="mt-1 text-muted">Answer: {q.answer_body}</p>
              ) : (
                <form
                  className="mt-2 space-y-2"
                  onSubmit={(e: FormEvent) => {
                    e.preventDefault()
                    const text = (answers[q.id] ?? '').trim()
                    if (text) answer.mutate({ id: q.id, text })
                  }}
                >
                  <textarea
                    className="min-h-16 w-full rounded-md border border-border bg-surface px-3 py-2"
                    value={answers[q.id] ?? ''}
                    onChange={(e) =>
                      setAnswers((prev) => ({
                        ...prev,
                        [q.id]: e.target.value,
                      }))
                    }
                    placeholder="Write an answer…"
                  />
                  <Button type="submit">Send answer</Button>
                </form>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
