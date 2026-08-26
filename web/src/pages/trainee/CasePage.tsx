import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ActionBar } from '@/components/ui/ActionBar'
import { Button } from '@/components/ui/Button'
import { CaseHeader } from '@/components/ui/CaseHeader'
import { CorrectionThreadList } from '@/components/ui/CorrectionThreadList'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonRows } from '@/components/ui/Skeleton'
import { PageHeader } from '@/components/ui/PageHeader'
import {
  askQuestion,
  getCase,
  listCaseResources,
  listCorrectionThreads,
  listQuestionsForCase,
  listRequirementsForCase,
  markFileSent,
  submitCaseForReview,
  unmarkFileSent,
} from '@/lib/api'
import { FILE_KIND_LABELS, FILE_STATUS_LABELS } from '@/lib/domain/revisions'
import { TRAINEE_OWNED_STATUSES } from '@/lib/domain/ownership'
import type { CaseStatus } from '@/lib/types'

export function TraineeCasePage() {
  const { caseId = '' } = useParams()
  const qc = useQueryClient()
  const [urls, setUrls] = useState<Record<string, string>>({})
  const [question, setQuestion] = useState('')
  const [message, setMessage] = useState<string | null>(null)

  const caseQ = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => getCase(caseId),
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
  const resourcesQ = useQuery({
    queryKey: ['resources', caseId],
    queryFn: () => listCaseResources(caseId),
    enabled: !!caseId,
  })

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['case', caseId] })
    void qc.invalidateQueries({ queryKey: ['requirements', caseId] })
    void qc.invalidateQueries({ queryKey: ['threads', caseId] })
    void qc.invalidateQueries({ queryKey: ['case-questions', caseId] })
    void qc.invalidateQueries({ queryKey: ['trainee-cases'] })
  }

  const saveLink = useMutation({
    mutationFn: async ({
      requirementId,
      url,
    }: {
      requirementId: string
      url: string
    }) => markFileSent(requirementId, url.trim() || null),
    onSuccess: () => {
      setMessage('Link saved.')
      invalidate()
    },
    onError: (e: Error) => setMessage(e.message),
  })

  const clearLink = useMutation({
    mutationFn: (requirementId: string) => unmarkFileSent(requirementId),
    onSuccess: () => {
      setMessage('Link cleared.')
      invalidate()
    },
  })

  const submit = useMutation({
    mutationFn: () => submitCaseForReview(caseId),
    onSuccess: () => {
      setMessage('Package submitted for review.')
      invalidate()
    },
    onError: (e: Error) => setMessage(e.message),
  })

  const ask = useMutation({
    mutationFn: () => askQuestion({ caseId, body: question.trim() }),
    onSuccess: () => {
      setQuestion('')
      setMessage('Question sent.')
      invalidate()
    },
    onError: (e: Error) => setMessage(e.message),
  })

  const caseRow = caseQ.data
  const canEdit = caseRow
    ? TRAINEE_OWNED_STATUSES.has(caseRow.status as CaseStatus)
    : false
  const canSubmit =
    caseRow?.status === 'assigned' ||
    caseRow?.status === 'submitted' ||
    caseRow?.status === 'awaiting_resubmission'

  if (caseQ.isLoading) return <SkeletonRows count={3} />
  if (!caseRow) {
    return (
      <EmptyState
        title="Case not found"
        description="It may be unassigned or outside your access."
      />
    )
  }

  if (caseRow.status === 'not_started') {
    return (
      <EmptyState
        title="Waiting for assignment"
        description="This case is not visible as work until your trainer assigns it."
      />
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Case workspace"
        description="Submit OneDrive links, read corrections, and ask questions."
        action={
          <Link to="/trainee" className="text-sm text-primary hover:underline">
            Back to my cases
          </Link>
        }
      />

      <CaseHeader caseRow={caseRow} role="trainee" />

      {message ? (
        <p className="rounded-md border border-border bg-surface-2 px-3 py-2 text-sm">
          {message}
        </p>
      ) : null}

      {(resourcesQ.data?.length ?? 0) > 0 ? (
        <section className="rounded-lg border border-border bg-surface p-4">
          <h3 className="font-semibold">Source material</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {resourcesQ.data!.map((r) => (
              <li key={r.id}>
                <a
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary hover:underline"
                >
                  {r.title}
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">Deliverables</h3>
        <p className="mt-1 text-sm text-muted">
          Paste OneDrive share links for PDF 1, PDF 2, and OV.
        </p>
        <div className="mt-4 space-y-4">
          {(reqQ.data ?? []).map((req) => {
            const label = FILE_KIND_LABELS[req.kind] ?? req.kind
            const value = urls[req.id] ?? req.external_url ?? ''
            return (
              <div
                key={req.id}
                className="rounded-md border border-border bg-bg p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">{label}</p>
                  <span className="text-xs text-muted">
                    {FILE_STATUS_LABELS[req.status] ?? req.status}
                  </span>
                </div>
                {req.replacement_reason ? (
                  <p className="mt-1 text-sm text-attention">
                    Replacement requested: {req.replacement_reason}
                  </p>
                ) : null}
                <input
                  className="mt-2 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
                  placeholder="https://…"
                  value={value}
                  disabled={!canEdit}
                  onChange={(e) =>
                    setUrls((prev) => ({ ...prev, [req.id]: e.target.value }))
                  }
                />
                {canEdit ? (
                  <div className="mt-2 flex gap-2">
                    <Button
                      onClick={() =>
                        saveLink.mutate({
                          requirementId: req.id,
                          url: urls[req.id] ?? req.external_url ?? '',
                        })
                      }
                    >
                      Save link
                    </Button>
                    {req.external_url ? (
                      <Button
                        variant="secondary"
                        onClick={() => clearLink.mutate(req.id)}
                      >
                        Clear
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
        {canSubmit ? (
          <ActionBar>
            <Button
              onClick={() => submit.mutate()}
              disabled={submit.isPending}
            >
              Submit package for review
            </Button>
          </ActionBar>
        ) : null}
      </section>

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">Corrections</h3>
        <CorrectionThreadList threads={threadsQ.data ?? []} />
      </section>

      <section className="rounded-lg border border-border bg-surface p-4">
        <h3 className="font-semibold">Ask a question</h3>
        <form
          className="mt-3 space-y-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            if (question.trim()) ask.mutate()
          }}
        >
          <textarea
            className="min-h-24 w-full rounded-md border border-border bg-bg px-3 py-2 text-sm"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask your trainer about this case…"
          />
          <Button type="submit" disabled={ask.isPending || !question.trim()}>
            Send question
          </Button>
        </form>
        <ul className="mt-4 space-y-2">
          {(questionsQ.data ?? []).map((q) => (
            <li
              key={q.id}
              className="rounded-md border border-border bg-bg p-3 text-sm"
            >
              <p className="font-medium">{q.body}</p>
              <p className="mt-1 text-xs text-muted">{q.status}</p>
              {q.answer_body ? (
                <p className="mt-2 text-muted">Answer: {q.answer_body}</p>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
