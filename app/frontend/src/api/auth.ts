import { getProtectedApi } from './client'

export interface AuthenticatedBackendIdentity {
  email: string | null
  user_id: string
}

export function getAuthenticatedBackendIdentity(): Promise<AuthenticatedBackendIdentity> {
  return getProtectedApi<AuthenticatedBackendIdentity>('/api/v1/auth/me')
}
