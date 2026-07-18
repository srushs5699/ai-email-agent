import { fireEvent, render, screen } from '@testing-library/react'
import type { Session } from '@supabase/supabase-js'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { ApiUnauthorizedError } from './api/client'

const supabaseAuthMocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  onAuthStateChange: vi.fn(),
  signInWithOAuth: vi.fn(),
  signOut: vi.fn(),
}))

const backendAuthMocks = vi.hoisted(() => ({
  getAuthenticatedBackendIdentity: vi.fn(),
}))

vi.mock('./lib/supabase', () => ({
  supabase: {
    auth: supabaseAuthMocks,
  },
}))

vi.mock('./api/health', () => ({
  getBackendHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
}))

vi.mock('./api/auth', () => ({
  getAuthenticatedBackendIdentity: backendAuthMocks.getAuthenticatedBackendIdentity,
}))

const authenticatedSession = {
  access_token: 'access-token-that-must-not-be-rendered',
  refresh_token: 'refresh-token-that-must-not-be-rendered',
  user: { email: 'person@example.com' },
} as Session

function arrangeAuth(session: Session | null, pending = false) {
  supabaseAuthMocks.getSession.mockImplementation(
    () =>
      pending
        ? new Promise(() => undefined)
        : Promise.resolve({ data: { session }, error: null }),
  )
  supabaseAuthMocks.onAuthStateChange.mockReturnValue({
    data: { subscription: { unsubscribe: vi.fn() } },
  })
  supabaseAuthMocks.signOut.mockResolvedValue({ error: null })
}

function renderAt(path: string) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

afterEach(() => {
  vi.clearAllMocks()
  window.history.pushState({}, '', '/')
})

beforeEach(() => {
  backendAuthMocks.getAuthenticatedBackendIdentity.mockResolvedValue({
    email: 'person@example.com',
    user_id: 'user-1',
  })
})

describe('App', () => {
  it('shows the login page to an unauthenticated user', async () => {
    arrangeAuth(null)
    renderAt('/login')

    expect(
      await screen.findByRole('button', { name: 'Continue with Google' }),
    ).toBeInTheDocument()
  })

  it('redirects an unauthenticated user from the dashboard to login', async () => {
    arrangeAuth(null)
    renderAt('/')

    expect(
      await screen.findByRole('button', { name: 'Continue with Google' }),
    ).toBeInTheDocument()
  })

  it('shows the protected dashboard to an authenticated user', async () => {
    arrangeAuth(authenticatedSession)
    renderAt('/')

    expect(
      await screen.findByText('Backend connected successfully.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Signed in as')).toBeInTheDocument()
    expect(
      await screen.findByText(
        'Signed-in backend identity confirmed for',
        { exact: false },
      ),
    ).toBeInTheDocument()
  })

  it('redirects an authenticated user from login to the dashboard', async () => {
    arrangeAuth(authenticatedSession)
    renderAt('/login')

    expect(
      await screen.findByText('Backend connected successfully.'),
    ).toBeInTheDocument()
  })

  it('shows an authentication-loading state while the session is restored', () => {
    arrangeAuth(null, true)
    renderAt('/')

    expect(screen.getByText('Checking authentication...')).toBeInTheDocument()
  })

  it('keeps the backend health-status behavior on the dashboard', async () => {
    arrangeAuth(authenticatedSession)
    renderAt('/')

    expect(
      await screen.findByText('Backend connected successfully.'),
    ).toBeInTheDocument()
  })

  it('shows a loading state while the protected backend identity is checked', async () => {
    backendAuthMocks.getAuthenticatedBackendIdentity.mockImplementation(
      () => new Promise(() => undefined),
    )
    arrangeAuth(authenticatedSession)
    renderAt('/')

    expect(
      await screen.findByText('Verifying signed-in backend session...'),
    ).toBeInTheDocument()
  })

  it('shows a safe message for a non-401 backend error', async () => {
    backendAuthMocks.getAuthenticatedBackendIdentity.mockRejectedValue(
      new Error('internal backend detail'),
    )
    arrangeAuth(authenticatedSession)
    renderAt('/')

    expect(
      await screen.findByText('Unable to verify your signed-in backend session.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('internal backend detail')).not.toBeInTheDocument()
  })

  it('signs out locally and returns to login when the backend returns 401', async () => {
    backendAuthMocks.getAuthenticatedBackendIdentity.mockRejectedValue(
      new ApiUnauthorizedError(),
    )
    arrangeAuth(authenticatedSession)
    renderAt('/')

    expect(
      await screen.findByRole('button', { name: 'Continue with Google' }),
    ).toBeInTheDocument()
    expect(supabaseAuthMocks.signOut).toHaveBeenCalledWith({ scope: 'local' })
    expect(
      screen.getByText('Your session is no longer valid. Please sign in again.'),
    ).toBeInTheDocument()
  })

  it('keeps access and refresh tokens out of the dashboard', async () => {
    arrangeAuth(authenticatedSession)
    renderAt('/')

    await screen.findByText('Signed-in backend identity confirmed for', {
      exact: false,
    })

    expect(
      screen.queryByText('access-token-that-must-not-be-rendered'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText('refresh-token-that-must-not-be-rendered'),
    ).not.toBeInTheDocument()
  })

  it('signs out from the dashboard', async () => {
    arrangeAuth(authenticatedSession)
    renderAt('/')

    fireEvent.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(
      await screen.findByRole('button', { name: 'Continue with Google' }),
    ).toBeInTheDocument()
    expect(supabaseAuthMocks.signOut).toHaveBeenCalledWith({ scope: 'local' })
  })
})
