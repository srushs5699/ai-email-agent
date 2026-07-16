import BackendStatus from './components/BackendStatus'
import AuthStatus from './components/AuthStatus'

function App() {
  return (
    <main>
      <h1>AI Email Agent</h1>
      <p>Project foundation is running.</p>

      <AuthStatus />
      <BackendStatus />
    </main>
  )
}

export default App
