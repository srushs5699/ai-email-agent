import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router'

import './App.css'

import { AuthProvider } from './auth/AuthProvider'
import { useAuth } from './auth/AuthContext'
import AuthenticatedBackendStatus from './components/AuthenticatedBackendStatus'
import BackendStatus from './components/BackendStatus'
import AuthStatus from './components/AuthStatus'
import { AppLayout } from './components/AppLayout'
import { OutreachPage } from './pages/OutreachPage'
import { ResumeLibraryPage } from './pages/ResumeLibraryPage'
import { ProcessingQueuePage } from './pages/ProcessingQueuePage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { FailedTasksQueuePage } from './pages/FailedTasksQueuePage'

function AuthenticationLoading() {
  return <main className="login-page" aria-live="polite"><p>Checking authentication...</p></main>
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isLoading, session } = useAuth()

  if (isLoading) {
    return <AuthenticationLoading />
  }

  return session ? <AppLayout>{children}</AppLayout> : <Navigate to="/login" replace />
}

function LoginPage() {
  const { isLoading, session } = useAuth()

  if (isLoading) {
    return <AuthenticationLoading />
  }

  if (session) {
    return <Navigate to="/" replace />
  }

  return (
    <main className="login-page">
      <h1>AI Email Agent</h1>
      <p>Sign in to continue to your dashboard.</p>
      <AuthStatus />
    </main>
  )
}

function AuthCallbackPage() {
  const { isLoading, session } = useAuth()

  if (isLoading) {
    return <AuthenticationLoading />
  }

  return <Navigate to={session ? '/' : '/login'} replace />
}

function DashboardPage() {
  const { session } = useAuth()
  return (
    <main className="page-container">
      <header className="page-header dashboard-hero">
        <p className="page-eyebrow">Dashboard</p>
        <h1>AI Email Agent</h1>
        <p>Create, review, and send personalized outreach emails from one workspace.</p>
      </header>
      <section className="dashboard-grid" aria-label="Quick actions">
        <article className="quick-card"><p className="card-eyebrow">Library</p><h2>Resume Library</h2><p className="card-description">Upload and choose the resume that guides your outreach.</p><Link className="button button--primary card-action" to="/resumes">Manage resumes <span aria-hidden="true">→</span></Link></article>
        <article className="quick-card"><p className="card-eyebrow">Create</p><h2>Compose Outreach</h2><p className="card-description">Create a personalized email and prepare it for review.</p><Link className="button button--primary card-action" to="/outreach">Create outreach <span aria-hidden="true">→</span></Link></article>
        <article className="quick-card"><p className="card-eyebrow">Batch work</p><h2>Processing Queue</h2><p className="card-description">Build and monitor batches of outreach requests.</p><Link className="button button--secondary card-action" to="/processing-queue">View processing queue <span aria-hidden="true">→</span></Link></article>
        <article className="quick-card"><p className="card-eyebrow">Approval</p><h2>Review Queue</h2><p className="card-description">Review generated drafts before explicitly sending them.</p><Link className="button button--secondary card-action" to="/review-queue">Review drafts <span aria-hidden="true">→</span></Link></article>
        <article className="quick-card"><p className="card-eyebrow">Attention</p><h2>Failed Tasks</h2><p className="card-description">Review and retry processing items that need attention.</p><Link className="button button--secondary card-action" to="/failed-tasks">View failed tasks <span aria-hidden="true">→</span></Link></article>
      </section>
      <section className="account-card" aria-labelledby="account-heading">
        <h2 id="account-heading">Account</h2>
        <p className="account-card__email">Signed in as <strong>{session?.user.email ?? 'Google user'}</strong></p>
        <div className="account-statuses">
          <p><span className="status-label">Authentication</span><span className="status-badge status-badge--success">Connected</span></p>
          <BackendStatus />
          <AuthenticatedBackendStatus showSuccess={false} />
        </div>
      </section>
    </main>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/resumes"
            element={
              <ProtectedRoute>
                <ResumeLibraryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/outreach"
            element={
              <ProtectedRoute>
                <OutreachPage />
              </ProtectedRoute>
            }
          />
          <Route path="/processing-queue" element={<ProtectedRoute><ProcessingQueuePage /></ProtectedRoute>} />
          <Route path="/review-queue" element={<ProtectedRoute><ReviewQueuePage /></ProtectedRoute>} />
          <Route path="/failed-tasks" element={<ProtectedRoute><FailedTasksQueuePage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
