import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageHeader } from '@/components/ui/PageHeader'
import { SkeletonRows } from '@/components/ui/Skeleton'
import { useAuth } from '@/hooks/useAuth'
import {
  getTraineeForUser,
  listQuestionsForTrainee,
  markQuestionViewed,
} from '@/lib/api'

export function TraineeQuestionsPage() {
  const { user } = useAuth()
  const traineeQ = useQuery({
    queryKey: ['trainee-for-user', user?.id],
    queryFn: () => getTraineeForUser(user!.id),
    enabled: !!user,
  })
  const questionsQ = useQuery({
    queryKey: ['trainee-questions', traineeQ.data?.id],
    queryFn: () => listQuestionsForTrainee(traineeQ.data!.id),
    enabled: !!traineeQ.data?.id,
  })

  return (
    <div>
      <PageHeader
        title="Questions"
        description="Answers from your trainer across all cases."
      />
      {questionsQ.isLoading ? (
        <SkeletonRows count={3} />
      ) : (questionsQ.data?.length ?? 0) === 0 ? (
        <EmptyState
          title="No questions yet"
          description="Ask from a case workspace when something is unclear."
        />
      ) : (
        <ul className="space-y-3">
          {questionsQ.data!.map((q) => (
            <li
              key={q.id}
              className="rounded-lg border border-border bg-surface p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="font-medium text-text">{q.body}</p>
                <span className="text-xs capitalize text-muted">{q.status}</span>
              </div>
              {q.answer_body ? (
                <p className="mt-2 text-sm text-muted">
                  <span className="font-medium text-text">Answer:</span>{' '}
                  {q.answer_body}
                </p>
              ) : (
                <p className="mt-2 text-sm text-muted">Waiting on trainer.</p>
              )}
              <Link
                to={`/trainee/cases/${q.case_id}`}
                className="mt-2 inline-block text-sm text-primary hover:underline"
                onClick={() => {
                  if (q.answer_body) void markQuestionViewed(q.id)
                }}
              >
                Open case
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
