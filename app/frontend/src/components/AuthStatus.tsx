import { useAuth } from '../auth/AuthContext'

function AuthStatus() {
  const { errorMessage, session, signInWithGoogle, signOut } = useAuth()

  return (
    <section className="auth-status" aria-labelledby="authentication-heading">
      <h2 id="authentication-heading">Authentication</h2>

      {session ? (
        <>
          <p>
            Signed in as{' '}
            <strong>{session.user.email ?? 'Google user'}</strong>
          </p>
          <button className="button button--secondary" type="button" onClick={() => void signOut()}>
            Sign out
          </button>
        </>
      ) : (
        <button className="button button--primary" type="button" onClick={() => void signInWithGoogle()}>
          Continue with Google
        </button>
      )}

      {errorMessage ? <p className="auth-status__error" role="alert">{errorMessage}</p> : null}
    </section>
  )
}

export default AuthStatus
