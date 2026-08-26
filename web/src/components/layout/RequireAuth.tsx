import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import type { AppRole } from '@/lib/types'

export function RequireAuth({ role }: { role?: AppRole }) {
  const { session, profile, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        Loading…
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  if (!profile) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4 text-center text-muted">
        Signed in, but no profile was found. Ask a trainer to set your role.
      </div>
    )
  }

  if (role && profile.role !== role) {
    return (
      <Navigate
        to={profile.role === 'trainer' ? '/trainer' : '/trainee'}
        replace
      />
    )
  }

  return <Outlet />
}
