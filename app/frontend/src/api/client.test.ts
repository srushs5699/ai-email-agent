import type { Session } from '@supabase/supabase-js'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiUnauthorizedError,
  MissingSessionError,
  getProtectedApi,
} from './client'
import { getBackendHealth } from './health'

const supabaseAuthMocks = vi.hoisted(() => ({
  getSession: vi.fn(),
}))

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: supabaseAuthMocks,
  },
}))

const activeSession = {
  access_token: 'access-token-that-must-not-be-rendered',
  refresh_token: 'refresh-token-that-must-not-be-rendered',
} as Session

describe('API client', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    supabaseAuthMocks.getSession.mockResolvedValue({
      data: { session: activeSession },
      error: null,
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('keeps the health request public', async () => {
    fetchMock.mockResolvedValue({
      json: vi.fn().mockResolvedValue({ status: 'healthy' }),
      ok: true,
      status: 200,
    })

    await expect(getBackendHealth()).resolves.toEqual({ status: 'healthy' })

    expect(supabaseAuthMocks.getSession).not.toHaveBeenCalled()
    expect(fetchMock).toHaveBeenCalledWith('https://api.test/health')
  })

  it('adds the current bearer token to a protected request', async () => {
    fetchMock.mockResolvedValue({
      json: vi.fn().mockResolvedValue({ email: 'person@example.com', user_id: 'user-1' }),
      ok: true,
      status: 200,
    })

    await expect(getProtectedApi('/api/v1/auth/me')).resolves.toEqual({
      email: 'person@example.com',
      user_id: 'user-1',
    })

    expect(fetchMock).toHaveBeenCalledWith('https://api.test/api/v1/auth/me', {
      headers: {
        Authorization: 'Bearer access-token-that-must-not-be-rendered',
      },
    })
  })

  it('does not make a protected request without a session', async () => {
    supabaseAuthMocks.getSession.mockResolvedValue({
      data: { session: null },
      error: null,
    })

    await expect(getProtectedApi('/api/v1/auth/me')).rejects.toBeInstanceOf(
      MissingSessionError,
    )

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('returns a consistent unauthorized error without exposing response details', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 401 })

    await expect(getProtectedApi('/api/v1/auth/me')).rejects.toBeInstanceOf(
      ApiUnauthorizedError,
    )
  })
})
