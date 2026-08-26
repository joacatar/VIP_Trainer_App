import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/Button'

function navClass({ isActive }: { isActive: boolean }) {
  return `block rounded-md px-3 py-2 text-sm ${
    isActive
      ? 'bg-white/10 font-medium text-white'
      : 'text-white/70 hover:bg-white/5 hover:text-white'
  }`
}

function readDark(): boolean {
  return document.documentElement.classList.contains('dark')
}

export function AppShell({
  links,
}: {
  links: Array<{ to: string; label: string }>
}) {
  const { profile, user, signOut } = useAuth()
  const [dark, setDark] = useState(readDark)

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 shrink-0 flex-col bg-sidebar text-white">
        <div className="border-b border-white/10 px-4 py-5">
          <p className="text-xs font-medium uppercase tracking-wider text-white/50">
            CT Training
          </p>
          <p className="mt-1 text-sm font-semibold">VIP Trainer</p>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to.split('/').length <= 2}
              className={navClass}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-white/10 p-3">
          <p className="truncate text-sm font-medium text-white">
            {profile?.full_name || user?.email}
          </p>
          <p className="text-xs capitalize text-white/50">{profile?.role}</p>
          <div className="mt-3 flex flex-col gap-2">
            <Button
              variant="ghost"
              className="justify-start px-2 text-white/70 hover:bg-white/10 hover:text-white"
              onClick={() => {
                document.documentElement.classList.toggle('dark')
                const next = readDark()
                localStorage.setItem('ct-theme', next ? 'dark' : 'light')
                setDark(next)
              }}
            >
              {dark ? 'Light mode' : 'Dark mode'}
            </Button>
            <Button
              variant="ghost"
              className="justify-start px-2 text-white/70 hover:bg-white/10 hover:text-white"
              onClick={() => void signOut()}
            >
              Sign out
            </Button>
          </div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-auto">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

export function TrainerShell() {
  return (
    <AppShell
      links={[
        { to: '/trainer', label: 'Dashboard' },
        { to: '/trainer/cases', label: 'Cases' },
        { to: '/trainer/trainees', label: 'Trainees' },
        { to: '/trainer/analytics', label: 'Analytics' },
      ]}
    />
  )
}

export function TraineeShell() {
  return (
    <AppShell
      links={[
        { to: '/trainee', label: 'My cases' },
        { to: '/trainee/corrections', label: 'My corrections' },
        { to: '/trainee/questions', label: 'Questions' },
      ]}
    />
  )
}
