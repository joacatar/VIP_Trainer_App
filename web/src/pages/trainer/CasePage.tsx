import { useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
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
 * Trainer review workspace — mirrors Streamlit's 3-step flow:
 * 1. Files  2. Raise corrections (draft)  3. Publish / Approve
 * Critical: never create an empty revision just to click Publish.
 */
export function TrainerCasePage() {
  const { caseId = '' } = useParams()
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
    return createRevision(caseId)
  }

  const raiseThread = useMutation({
    mutationFn: async () => {
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
      return threadId
    },
    onSuccess: () => {
      setBody('')
      setPendingImages([])
      flash(
        'Correction saved to draft. When you are done with all sections, click “Publish review & notify trainee” below.',
      )
      invalidate()
    },
    onError: (e: Error) => flash(e.message, 'err'),
  })

  const attachShots = useMutation({
    mutationFn: async ({
      threadId,
      images,
    }: {
      threadId: string
      images: File[]
    }) => uploadPending(threadId, images),
    onSuccess: (_d, vars) => {
      flash(`Attached ${vars.images.length} screenshot(s).`)
      invalidate()
    },
    onError: (e: Error) => flash(e.message, 'err'),
  })

  const publish = useMutation({
    mutationFn: async (approve: boolean) => {
      if (approve) {
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
          revisionId: draftRevisionId,
          fileDecisions: acceptAll,
          approvePackage: true,
        })
        return { approve: true as const }
      }

      // Match Streamlit: only publish when there is a draft revision and/or
      // file replacements. Never invent an empty revision just to click Publish.
      if (!draftRevisionId && replacementCount === 0) {
        throw new Error(
          'Nothing to publish yet. Raise at least one correction (Save feedback) or mark a file for replacement, then publish.',
        )
      }

      const revisionId = draftRevisionId
      await publishCaseReview({
        caseId,
        revisionId,
        approvePackage: false,
      })
      if (revisionId && openThreads.length > 0) {
        await markOpenThreadsStillOpen(caseId, revisionId)
      }
      return { approve: false as const }
    },
    onSuccess: (result) => {
      if (result.approve) {
        flash('Case approved. Trainee is done with this case.')
      } else {
        flash(
          'Review published — trainee has been notified. Status is now corrections_sent / awaiting resubmission.',
        )
      }
      invalidate()
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
          : 'Replacement requested — remember to Publish review to send the package back.',
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
  const canPublish =
    canReview && (Boolean(draftRevisionId) || replacementCount > 0)
  const canApprove =
    canReview && openThreads.length === 0 && replacementCount === 0

  return (
    <div className="space-y-6 pb-28">
      <PageHeader
        title="Review workspace"
        description="1) Check files · 2) Raise corrections · 3) Publish to notify the trainee."
        action={
          <Link
            to={`/trainer/cases?trainee=${caseRow.trainee_id ?? ''}`}
            className="text-sm text-primary hover:underline"
          >
            Back to cases
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
        <NextStepCallout title="This case is not in review">
          Status is <strong>{caseRow.status}</strong>. You can only raise and
          publish corrections when the case is <strong>in review</strong> or{' '}
          <strong>corrections sent</strong>.
          {caseRow.status === 'approved'
            ? ' This case is already approved — it cannot be sent back unless you reopen it from the database.'
            : null}
        </NextStepCallout>
      ) : draftRevisionId ? (
        <NextStepCallout title="Draft ready to send">
          You have a draft revision with {openThreads.length} open correction
          {openThreads.length === 1 ? '' : 's'}
          {replacementCount > 0
            ? ` and ${replacementCount} file replacement${replacementCount === 1 ? '' : 's'}`
            : ''}
          . Scroll to <strong>3. Finish</strong> and click{' '}
          <strong>Publish review & notify trainee</strong>.
        </NextStepCallout>
      ) : openThreads.length > 0 ? (
        <NextStepCallout title="Corrections already with trainee">
          This case is <strong>{caseRow.status}</strong> with{' '}
          {openThreads.length} open correction
          {openThreads.length === 1 ? '' : 's'}. The trainee should already see
          them. To send <em>more</em> feedback, raise new corrections below
          (that starts a new draft), then Publish again.
        </NextStepCallout>
      ) : null}

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">1. Files</h3>
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
                        decision: 'replacement_requested',
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
      </section>

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">2. Raise corrections</h3>
        <p className="mt-1 text-sm text-muted">
          Pick a section, optionally click checklist items, paste screenshots,
          then <strong>Save feedback</strong>. Repeat for each section. Nothing
          is sent to the trainee until you Publish in step 3.
        </p>

        {!canReview ? (
          <p className="mt-3 text-sm text-muted">
            Raising is disabled while the case is not in review.
          </p>
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
                placeholder={`Correction for ${SECTION_LABELS[section]}… Paste screenshots with Ctrl+V / Cmd+V`}
                disabled={raiseThread.isPending}
              />
            </div>
            <ActionBar>
              <Button
                disabled={
                  (!body.trim() && pendingImages.length === 0) ||
                  raiseThread.isPending
                }
                onClick={() => raiseThread.mutate()}
              >
                {raiseThread.isPending ? 'Saving…' : 'Save feedback'}
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
          attaching={attachShots.isPending}
          onAttachScreenshots={
            canReview
              ? async (threadId, images) => {
                  await attachShots.mutateAsync({ threadId, images })
                }
              : undefined
          }
        />
      </section>

      {canReview ? (
        <section className="sticky bottom-0 z-20 -mx-6 border-t border-border bg-surface/95 px-6 py-4 shadow-[0_-8px_24px_rgba(0,0,0,0.08)] backdrop-blur">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
            <div className="text-sm">
              <p className="font-semibold">3. Finish</p>
              <p className="text-muted">
                {canPublish
                  ? `${draftRevisionId ? 'Draft revision ready' : 'File replacements marked'}${
                      openThreads.length
                        ? ` · ${openThreads.length} open correction(s)`
                        : ''
                    }`
                  : 'Raise corrections or mark file replacements first.'}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={!canPublish || publish.isPending}
                onClick={() => publish.mutate(false)}
              >
                {publish.isPending
                  ? 'Publishing…'
                  : 'Publish review & notify trainee'}
              </Button>
              <Button
                variant="secondary"
                disabled={!canApprove || publish.isPending}
                title={
                  !canApprove
                    ? openThreads.length > 0
                      ? 'Resolve open corrections first'
                      : 'Clear replacement marks first'
                    : undefined
                }
                onClick={() => publish.mutate(true)}
              >
                Approve case
              </Button>
            </div>
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
