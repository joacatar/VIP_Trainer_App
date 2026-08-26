import { Navigate, Route, Routes } from 'react-router-dom'
import { TrainerShell, TraineeShell } from '@/components/layout/AppShell'
import { RequireAuth } from '@/components/layout/RequireAuth'
import { useAuth } from '@/hooks/useAuth'
import { LoginPage } from '@/pages/LoginPage'
import { TraineeCasePage } from '@/pages/trainee/CasePage'
import { TraineeCorrectionsPage } from '@/pages/trainee/CorrectionsPage'
import { TraineeDashboardPage } from '@/pages/trainee/DashboardPage'
import { TraineeQuestionsPage } from '@/pages/trainee/QuestionsPage'
import { TrainerAnalyticsPage } from '@/pages/trainer/AnalyticsPage'
import { TrainerCasePage } from '@/pages/trainer/CasePage'
import { TrainerCasesPage } from '@/pages/trainer/CasesPage'
import { TrainerDashboardPage } from '@/pages/trainer/DashboardPage'
import { TrainerTraineesPage } from '@/pages/trainer/TraineesPage'

function HomeRedirect() {
  const { profile, loading, session } = useAuth()
  if (loading) return null
  if (!session) return <Navigate to="/login" replace />
  if (profile?.role === 'trainer') return <Navigate to="/trainer" replace />
  return <Navigate to="/trainee" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<HomeRedirect />} />

      <Route element={<RequireAuth role="trainer" />}>
        <Route element={<TrainerShell />}>
          <Route path="/trainer" element={<TrainerDashboardPage />} />
          <Route path="/trainer/cases" element={<TrainerCasesPage />} />
          <Route path="/trainer/cases/:caseId" element={<TrainerCasePage />} />
          <Route path="/trainer/trainees" element={<TrainerTraineesPage />} />
          <Route path="/trainer/analytics" element={<TrainerAnalyticsPage />} />
        </Route>
      </Route>

      <Route element={<RequireAuth role="trainee" />}>
        <Route element={<TraineeShell />}>
          <Route path="/trainee" element={<TraineeDashboardPage />} />
          <Route path="/trainee/cases/:caseId" element={<TraineeCasePage />} />
          <Route path="/trainee/questions" element={<TraineeQuestionsPage />} />
          <Route
            path="/trainee/corrections"
            element={<TraineeCorrectionsPage />}
          />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
