import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { useAuth } from '@/hooks/useAuth'
import { createTrainee, listActiveTrainees } from '@/lib/api'

export function TrainerTraineesPage() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [startDate, setStartDate] = useState(
    () => new Date().toISOString().slice(0, 10),
  )
  const [timezone, setTimezone] = useState('Australia/Sydney')
  const [isTest, setIsTest] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const traineesQ = useQuery({
    queryKey: ['trainees'],
    queryFn: listActiveTrainees,
  })

  const create = useMutation({
    mutationFn: () =>
      createTrainee({
        full_name: fullName.trim(),
        email: email.trim() || null,
        start_date: startDate,
        timezone,
        created_by: user!.id,
        is_test: isTest,
      }),
    onSuccess: () => {
      setMsg('Trainee created with phase-1 cases.')
      setFullName('')
      setEmail('')
      void qc.invalidateQueries({ queryKey: ['trainees'] })
      void qc.invalidateQueries({ queryKey: ['progress'] })
    },
    onError: (e: Error) => setMsg(e.message),
  })

  return (
    <div className="space-y-8">
      <PageHeader
        title="Trainees"
        description="Add a trainee to generate the 32 phase-1 cases automatically."
      />

      <form
        className="max-w-lg space-y-3 rounded-lg border border-border bg-surface p-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          if (!fullName.trim()) {
            setMsg('Name is required.')
            return
          }
          create.mutate()
        }}
      >
        <h2 className="font-semibold">Add trainee</h2>
        <label className="block text-sm">
          Full name
          <input
            required
            className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          Email
          <input
            type="email"
            className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          Start date
          <input
            type="date"
            required
            className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          Timezone
          <input
            className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={isTest}
            onChange={(e) => setIsTest(e.target.checked)}
          />
          Test trainee
        </label>
        {msg ? <p className="text-sm text-muted">{msg}</p> : null}
        <Button type="submit" disabled={create.isPending}>
          Create trainee
        </Button>
      </form>

      <section>
        <h2 className="mb-3 font-semibold">Active trainees</h2>
        <ul className="space-y-2">
          {(traineesQ.data ?? []).map((t) => (
            <li
              key={t.id}
              className="rounded-lg border border-border bg-surface px-4 py-3 text-sm"
            >
              <p className="font-medium">
                {t.full_name}
                {t.is_test ? ' · test' : ''}
              </p>
              <p className="text-muted">
                {t.email || 'No email'} · start {t.start_date}
                {t.phase_2_started_on
                  ? ` · phase 2 since ${t.phase_2_started_on}`
                  : ''}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
