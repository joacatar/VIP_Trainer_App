import { useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/hooks/useAuth'

export function LoginPage() {
  const { session, profile, signIn, loading, error } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  if (!loading && session && profile) {
    const dest =
      (location.state as { from?: { pathname?: string } } | null)?.from
        ?.pathname ?? (profile.role === 'trainer' ? '/trainer' : '/trainee')
    return <Navigate to={dest} replace />
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setLocalError(null)
    if (!email.trim() || !password) {
      setLocalError('Enter email and password.')
      return
    }
    setBusy(true)
    try {
      await signIn(email, password)
    } catch (err) {
      setLocalError(
        err instanceof Error ? err.message : 'Sign-in failed. Try again.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4">
      <div className="w-full max-w-md rounded-xl border border-border bg-surface p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-primary">
          CT Planning
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-text">VIP Trainer</h1>
        <p className="mt-1 text-sm text-muted">
          Sign in to continue training cases and reviews.
        </p>

        <form className="mt-8 space-y-4" onSubmit={(e) => void onSubmit(e)}>
          <label className="block">
            <span className="text-sm font-medium text-text">Email</span>
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-text outline-none focus:border-primary"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-text">Password</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2 text-text outline-none focus:border-primary"
            />
          </label>
          {(localError || error) && (
            <p className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {localError || error}
            </p>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={busy}
            onClick={() => undefined}
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </div>
    </div>
  )
}
