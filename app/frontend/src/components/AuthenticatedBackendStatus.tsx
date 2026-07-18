import { useEffect, useState } from 'react'

import { getAuthenticatedBackendIdentity } from '../api/auth'
import { ApiUnauthorizedError } from '../api/client'
import { useAuth } from '../auth/AuthContext'

type IdentityState =
  | { status: 'checking' }
  | { email: string | null; status: 'confirmed' }
  | { message: string; status: 'failed' }

function AuthenticatedBackendStatus() {
  const { handleExpiredSession, session } = useAuth()
  const [identityState, setIdentityState] = useState<IdentityState>({
    status: 'checking',
  })

  useEffect(() => {
    let isActive = true

    async function verifyIdentity(): Promise<void> {
      if (!session) {
        return
      }

      setIdentityState({ status: 'checking' })

      try {
        const identity = await getAuthenticatedBackendIdentity()

        if (isActive) {
          setIdentityState({ email: identity.email, status: 'confirmed' })
        }
      } catch (error) {
        if (!isActive) {
          return
        }

        if (error instanceof ApiUnauthorizedError) {
          setIdentityState({
            message: 'Your session is no longer valid. Please sign in again.',
            status: 'failed',
          })
          await handleExpiredSession()
          return
        }

        setIdentityState({
          message: 'Unable to verify your signed-in backend session.',
          status: 'failed',
        })
      }
    }

    void verifyIdentity()

    return () => {
      isActive = false
    }
  }, [handleExpiredSession, session])

  if (identityState.status === 'checking') {
    return <p>Verifying signed-in backend session...</p>
  }

  if (identityState.status === 'failed') {
    return <p role="alert">{identityState.message}</p>
  }

  return (
    <p>
      Signed-in backend identity confirmed for{' '}
      <strong>{identityState.email ?? 'your account'}</strong>.
    </p>
  )
}

export default AuthenticatedBackendStatus
