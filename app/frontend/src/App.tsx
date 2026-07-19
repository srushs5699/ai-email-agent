import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router'

import { AuthProvider } from './auth/AuthProvider'
import { useAuth } from './auth/AuthContext'
import AuthenticatedBackendStatus from './components/AuthenticatedBackendStatus'
import BackendStatus from './components/BackendStatus'
import AuthStatus from './components/AuthStatus'
import { OutreachPage } from './pages/OutreachPage'
import { ResumeLibraryPage } from './pages/ResumeLibraryPage'
import { ProcessingQueuePage } from './pages/ProcessingQueuePage'

function AuthenticationLoading() {
  return <p>Checking authentication...</p>
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isLoading, session } = useAuth()

  if (isLoading) {
    return <AuthenticationLoading />
  }

  return session ? children : <Navigate to="/login" replace />
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
    <main>
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
  return (
    <main>
      <h1>AI Email Agent</h1>
      <p>Prepare a resume, generate an outreach email, then copy it into Gmail.</p>

      <nav aria-label="Application">
        <Link to="/resumes">Resume Library</Link> <Link to="/outreach">Compose outreach</Link> <Link to="/processing-queue">Processing Queue</Link>
      </nav>

      <AuthStatus />
      <BackendStatus />
      <AuthenticatedBackendStatus />
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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
