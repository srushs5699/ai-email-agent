import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Session } from '@supabase/supabase-js'

import { AuthContext } from './AuthContext'
import { supabase } from '../lib/supabase'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    let isMounted = true

    void supabase.auth.getSession().then(({ data, error }) => {
      if (!isMounted) {
        return
      }

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
      isMounted = false
      subscription.unsubscribe()
    }
  }, [])

  const signInWithGoogle = useCallback(async () => {
    setErrorMessage('')

    const redirectTo =
      import.meta.env.VITE_AUTH_REDIRECT_URL ??
      `${window.location.origin}/auth/callback`

    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo },
    })

    if (error) {
      setErrorMessage(error.message)
    }
  }, [])

  const signOut = useCallback(async () => {
    setErrorMessage('')

    const { error } = await supabase.auth.signOut({ scope: 'local' })

    if (error) {
      setErrorMessage(error.message)
      return
    }

    setSession(null)
  }, [])

  const handleExpiredSession = useCallback(async () => {
    setErrorMessage('Your session is no longer valid. Please sign in again.')
    await supabase.auth.signOut({ scope: 'local' })
    setSession(null)
  }, [])

  const value = useMemo(
    () => ({
      errorMessage,
      handleExpiredSession,
      isLoading,
      session,
      signInWithGoogle,
      signOut,
    }),
    [
      errorMessage,
      handleExpiredSession,
      isLoading,
      session,
      signInWithGoogle,
      signOut,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
