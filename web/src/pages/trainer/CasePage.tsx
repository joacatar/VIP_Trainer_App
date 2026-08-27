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
  getNextNeedsYouCaseId,
  getTrainee,
  listCorrectionThreads,
  listQuestionsForCase,
  listRequirementsForCase,
  listRevisionsForCase,
  markOpenThreadsStillOpen,
  publishCaseReview,
  resolveThread,
  touchCaseOpened,
  uploadThreadScreenshot,
} from '@/lib/api'
import {
  FILE_KIND_LABELS,
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
 * Corrections-first review: work open threads, optionally add one new
 * correction, Approve when clean. No per-file accept/replace. After send →
 * next Needs you case.
 */
export function TrainerCasePage() {
  const { caseId = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { user } = useAuth()
  const [showAdd, setShowAdd] = useState(false)
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

  useEffect(() => {
    if (!caseId) return
    void touchCaseOpened(caseId).catch(() => {})
    void discardEmptyDraftRevisions(caseId)
      .then(() => qc.invalidateQueries({ queryKey: ['revisions', caseId] }))
      .catch(() => {})
  }, [caseId, qc])

  const ownerUserId =
    ownerQ.data ?? traineeQ.data?.auth_user_id ?? user?.id ?? ''

  const draftRevisionId = useMemo(() => {
    const draft = (revisionsQ.data ?? []).find((r) => r.status === 'draft')
    return (draft?.id as string | undefined) ?? null
  }, [revisionsQ.data])

  const openThreads = useMemo(
    () => (threadsQ.data ?? []).filter((t) => t.status !== 'resolved'),
    [threadsQ.data],
  )

  const roundNo = useMemo(() => {
    const published = (revisionsQ.data ?? []).filter(
      (r) => r.status === 'published',
    ).length
    return Math.max(1, published + (caseQ.data?.status === 'in_review' ? 1 : 0))
  }, [revisionsQ.data, caseQ.data?.status])

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['case', caseId] })
    void qc.invalidateQueries({ queryKey: ['requirements', caseId] })
    void qc.invalidateQueries({ queryKey: ['threads', caseId] })
    void qc.invalidateQueries({ queryKey: ['case-questions', caseId] })
    void qc.invalidateQueries({ queryKey: ['revisions', caseId] })
    void qc.invalidateQueries({ queryKey: ['trainer-queue'] })
    void qc.invalidateQueries({ queryKey: ['progress'] })
    void qc.invalidateQueries({ queryKey: ['screenshot-urls'] })
  }

  const flash = (text: string, tone: 'ok' | 'err' = 'ok') => {
    setMsg(text)
    setMsgTone(tone)
  }

  async function goToNextCase(nextId: string | null) {
    invalidate()
    if (nextId && nextId !== caseId) {
      navigate(`/trainer/cases/${nextId}`)
    } else {
      navigate('/trainer/cases?tab=needs_you')
    }
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
      const nextId = await getNextNeedsYouCaseId(caseId)
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
      return nextId
    },
    onSuccess: (nextId) => {
      setBody('')
      setPendingImages([])
      setShowAdd(false)
      flash('Sent — opening next case…')
      void goToNextCase(nextId)
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
      const nextId = await getNextNeedsYouCaseId(caseId)
      const revisionId = await ensureDraftRevisionId()
      await uploadPending(threadId, images)
      await publishAndNotify(revisionId)
      return nextId
    },
    onSuccess: (nextId) => {
      flash('Update sent — opening next case…')
      void goToNextCase(nextId)
    },
    onError: (e: Error) => flash(e.message, 'err'),
  })

  const approve = useMutation({
    mutationFn: async () => {
      const nextId = await getNextNeedsYouCaseId(caseId)
      await discardEmptyDraftRevisions(caseId)
      await publishCaseReview({
        caseId,
        revisionId: null,
        fileDecisions: [],
        approvePackage: true,
      })
      return nextId
    },
    onSuccess: (nextId) => {
      flash('Approved — opening next case…')
      void goToNextCase(nextId)
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
  const canApprove = canReview && openThreads.length === 0
  const busy =
    sendCorrection.isPending ||
    sendThreadUpdate.isPending ||
    approve.isPending

  return (
    <div className="space-y-6 pb-28">
      <PageHeader
        title="Review"
        description={`Round ${roundNo} — work open corrections, or add one if you spot something new.`}
        action={
          <Link
            to="/trainer/cases?tab=needs_you"
            className="text-sm text-primary hover:underline"
          >
            Needs you
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
          Status is <strong>{caseRow.status}</strong>. Send / Approve only work
          when the case is <strong>in review</strong>.
          {caseRow.status === 'approved'
            ? ' Already approved.'
            : null}
        </NextStepCallout>
      ) : openThreads.length > 0 ? (
        <NextStepCallout title={`Round ${roundNo} — open corrections`}>
          Resolve what the trainee fixed, or attach a screenshot and{' '}
          <strong>Send update</strong> on a thread that is still wrong. Add a
          new correction only if you spot something new.
        </NextStepCallout>
      ) : (
        <NextStepCallout title={`Round ${roundNo} — clear`}>
          No open corrections. Approve the case, or add a new correction if
          something is still wrong.
        </NextStepCallout>
      )}

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">Files (open only)</h3>
        <p className="mt-1 text-sm text-muted">
          Links for reference — no per-file accept / replace. Corrections carry
          the feedback.
        </p>
        <ul className="mt-3 space-y-2">
          {(reqQ.data ?? []).map((req) => (
            <li
              key={req.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-bg px-3 py-2 text-sm"
            >
              <span className="font-medium">
                {FILE_KIND_LABELS[req.kind] ?? req.kind}
              </span>
              {req.external_url ? (
                <a
                  href={req.external_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary hover:underline"
                >
                  Open OneDrive
                </a>
              ) : (
                <span className="text-muted">No link</span>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">
          Corrections ({openThreads.length} open)
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
        <section className="rounded-lg border border-border bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-semibold">Add a correction</h3>
            <Button
              variant="secondary"
              onClick={() => setShowAdd((v) => !v)}
            >
              {showAdd ? 'Hide' : 'Something new'}
            </Button>
          </div>
          {showAdd ? (
            <>
              <p className="mt-2 text-sm text-muted">
                Sends immediately and opens the next case in Needs you.
              </p>
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
                  placeholder={`Correction for ${SECTION_LABELS[section]}…`}
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
                  {sendCorrection.isPending
                    ? 'Sending…'
                    : 'Send correction → next'}
                </Button>
              </ActionBar>
            </>
          ) : null}
        </section>
      ) : null}

      {canReview ? (
        <section className="sticky bottom-0 z-20 -mx-6 border-t border-border bg-surface/95 px-6 py-4 shadow-[0_-8px_24px_rgba(0,0,0,0.08)] backdrop-blur">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
            <div className="text-sm">
              <p className="font-semibold">Finish</p>
              <p className="text-muted">
                {canApprove
                  ? 'All corrections resolved — approve when the package is good.'
                  : 'Resolve or send updates on open corrections before approving.'}
              </p>
            </div>
            <Button
              disabled={!canApprove || busy}
              onClick={() => approve.mutate()}
            >
              {approve.isPending ? 'Approving…' : 'Approve → next'}
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
