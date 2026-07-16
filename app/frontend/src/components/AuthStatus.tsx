import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'

import { supabase } from '../lib/supabase'

function AuthStatus() {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    void supabase.auth.getSession().then(({ data, error }) => {
      if (error) {
        setErrorMessage(error.message)
      }

      setSession(data.session)
      setIsLoading(false)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      setIsLoading(false)
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [])

  const handleGoogleSignIn = async () => {
    setErrorMessage('')

    const redirectTo =
      import.meta.env.VITE_AUTH_REDIRECT_URL ??
      `${window.location.origin}/auth/callback`

    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo,
      },
    })

    if (error) {
      setErrorMessage(error.message)
    }
  }

  const handleSignOut = async () => {
    setErrorMessage('')

    const { error } = await supabase.auth.signOut({
      scope: 'local',
    })

    if (error) {
      setErrorMessage(error.message)
    }
  }

  if (isLoading) {
    return <p>Checking authentication...</p>
  }

  return (
    <section aria-labelledby="authentication-heading">
      <h2 id="authentication-heading">Authentication</h2>

      {session ? (
        <>
          <p>
            Signed in as{' '}
            <strong>{session.user.email ?? 'Google user'}</strong>
          </p>
          <button type="button" onClick={() => void handleSignOut()}>
            Sign out
          </button>
        </>
      ) : (
        <button type="button" onClick={() => void handleGoogleSignIn()}>
          Continue with Google
        </button>
      )}

      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
    </section>
  )
}

export default AuthStatus
