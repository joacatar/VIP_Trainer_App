import { useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ActionBar } from '@/components/ui/ActionBar'
import { Button } from '@/components/ui/Button'
import { CaseHeader } from '@/components/ui/CaseHeader'
import { CorrectionThreadList } from '@/components/ui/CorrectionThreadList'
import { EmptyState } from '@/components/ui/EmptyState'
import { ImageAttachments } from '@/components/ui/ImageAttachments'
import { SkeletonRows } from '@/components/ui/Skeleton'
import { PageHeader } from '@/components/ui/PageHeader'
import { useAuth } from '@/hooks/useAuth'
import {
  answerQuestion,
  createCorrectionThread,
  createRevision,
  getCase,
  getTrainee,
  listCorrectionThreads,
  listQuestionsForCase,
  listRequirementsForCase,
  listRevisionsForCase,
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
import { pastedImageFilename } from '@/lib/domain/screenshots'

const PASTE_HINT = 'Paste screenshots here (Ctrl+V / Cmd+V), Jira-style.'

export function TrainerCasePage() {
  const { caseId = '' } = useParams()
  const qc = useQueryClient()
  const { user } = useAuth()
  const [section, setSection] = useState<string>(REVIEW_SECTIONS[0].key)
  const [body, setBody] = useState('')
  const [pendingImages, setPendingImages] = useState<File[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [msg, setMsg] = useState<string | null>(null)

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

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['case', caseId] })
    void qc.invalidateQueries({ queryKey: ['requirements', caseId] })
    void qc.invalidateQueries({ queryKey: ['threads', caseId] })
    void qc.invalidateQueries({ queryKey: ['case-questions', caseId] })
    void qc.invalidateQueries({ queryKey: ['revisions', caseId] })
    void qc.invalidateQueries({ queryKey: ['trainer-cases'] })
    void qc.invalidateQueries({ queryKey: ['progress'] })
  }

  const draftRevisionId = useMemo(() => {
    const rows = revisionsQ.data ?? []
    const draft = rows.find((r) => r.status === 'draft')
    return (draft?.id as string | undefined) ?? null
  }, [revisionsQ.data])

  const ensureRevision = useMutation({
    mutationFn: async () => {
      if (draftRevisionId) return draftRevisionId
      return createRevision(caseId)
    },
  })

  const raiseThread = useMutation({
    mutationFn: async () => {
      const revisionId = await ensureRevision.mutateAsync()
      const threadId = await createCorrectionThread({
        caseId,
        section,
        // A screenshot-only correction is valid — Streamlit's version
        // defaults the body the same way rather than blocking the raise.
        body: body.trim() || 'See attached screenshot(s).',
        revisionId,
      })
      if (pendingImages.length > 0) {
        const ownerUserId = traineeQ.data?.auth_user_id ?? user?.id ?? ''
        for (const file of pendingImages) {
          await uploadThreadScreenshot({
            threadId,
            caseId,
            ownerUserId,
            uploadedBy: user?.id ?? '',
            file,
          })
        }
      }
      return threadId
    },
    onSuccess: () => {
      setBody('')
      setPendingImages([])
      setMsg('Correction raised.')
      invalidate()
    },
    onError: (e: Error) => setMsg(e.message),
  })

  const publish = useMutation({
    mutationFn: async (approve: boolean) => {
      let revisionId = draftRevisionId
      if (!revisionId && !approve) {
        revisionId = await createRevision(caseId)
      }
      await publishCaseReview({
        caseId,
        revisionId,
        approvePackage: approve,
      })
    },
    onSuccess: () => {
      setMsg('Review published.')
      invalidate()
    },
    onError: (e: Error) => setMsg(e.message),
  })

  const fileDecision = useMutation({
    mutationFn: (input: {
      requirementId: string
      decision: string
      note?: string
    }) => reviewFileRequirement(input),
    onSuccess: () => invalidate(),
    onError: (e: Error) => setMsg(e.message),
  })

  const answer = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) =>
      answerQuestion(id, text),
    onSuccess: () => {
      setMsg('Answer sent.')
      invalidate()
    },
  })

  const resolve = useMutation({
    mutationFn: (threadId: string) => resolveThread(threadId, draftRevisionId),
    onSuccess: () => invalidate(),
    onError: (e: Error) => setMsg(e.message),
  })

  const caseRow = caseQ.data
  if (caseQ.isLoading) return <SkeletonRows count={3} />
  if (!caseRow) {
    return <EmptyState title="Case not found" />
  }

  const checklists = SECTION_CHECKLISTS[section] ?? []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Review workspace"
        description="Files, corrections by section, publish feedback or approve."
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
        <p className="rounded-md border border-border bg-surface-2 px-3 py-2 text-sm">
          {msg}
        </p>
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
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">Raise correction</h3>
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
        <textarea
          className="mt-3 min-h-24 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onPaste={(e) => {
            const items = e.clipboardData?.items
            if (!items) return
            const images: File[] = []
            for (const item of items) {
              if (!item.type.startsWith('image/')) continue
              const file = item.getAsFile()
              if (!file) continue
              images.push(
                new File(
                  [file],
                  pastedImageFilename(item.type, pendingImages.length + images.length + 1),
                  { type: item.type },
                ),
              )
            }
            if (images.length > 0) {
              e.preventDefault()
              setPendingImages((prev) => [...prev, ...images])
            }
          }}
          placeholder={`Correction for ${SECTION_LABELS[section]}… ${PASTE_HINT}`}
        />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <label className="cursor-pointer text-xs font-medium text-primary hover:underline">
            Upload screenshots
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              multiple
              className="hidden"
              onChange={(e) => {
                const files = Array.from(e.target.files ?? [])
                if (files.length > 0) {
                  setPendingImages((prev) => [...prev, ...files])
                }
                e.target.value = ''
              }}
            />
          </label>
          <span className="text-xs text-muted">or {PASTE_HINT.toLowerCase()}</span>
        </div>
        <ImageAttachments
          files={pendingImages}
          onRemove={(i) =>
            setPendingImages((prev) => prev.filter((_, idx) => idx !== i))
          }
        />
        <ActionBar>
          <Button
            disabled={
              (!body.trim() && pendingImages.length === 0) ||
              raiseThread.isPending
            }
            onClick={() => raiseThread.mutate()}
          >
            Raise correction
          </Button>
          <Button
            variant="secondary"
            disabled={publish.isPending}
            onClick={() => publish.mutate(false)}
          >
            Publish feedback
          </Button>
          <Button
            variant="secondary"
            disabled={publish.isPending}
            onClick={() => publish.mutate(true)}
          >
            Approve package
          </Button>
        </ActionBar>
      </section>

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">Correction threads</h3>
        <CorrectionThreadList
          threads={threadsQ.data ?? []}
          onResolve={(id) => resolve.mutate(id)}
          resolving={resolve.isPending}
        />
      </section>

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
                      setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
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
