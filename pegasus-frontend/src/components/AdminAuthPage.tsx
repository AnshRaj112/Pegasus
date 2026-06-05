import { useState } from 'react'
import { adminLogin, adminSignup } from '../api/adminAuth'

export default function AdminAuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = { email: email.trim(), password }
      const user = mode === 'signup'
        ? await adminSignup(payload)
        : await adminLogin(payload)
      onAuthenticated(user)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'var(--surface-0)' }}>
      <form onSubmit={handleSubmit} style={{ width: 420, maxWidth: '92vw', background: 'var(--surface-1)', border: '1px solid var(--border-1)', borderRadius: 12, padding: 20, display: 'grid', gap: 12 }}>
        <h2 style={{ margin: 0, color: 'var(--text-1)' }}>Admin {mode === 'signup' ? 'Signup' : 'Login'}</h2>
        <p style={{ margin: 0, color: 'var(--text-3)', fontSize: 12 }}>
          {mode === 'signup'
            ? 'Create the first admin account.'
            : 'Sign in to access admin features.'}
        </p>
        <input className="input input-mono" type="email" placeholder="admin@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="input input-mono" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Please wait...' : mode === 'signup' ? 'Create account' : 'Login'}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => setMode((m) => (m === 'signup' ? 'login' : 'signup'))}>
          {mode === 'signup' ? 'Already have an account? Login' : 'First time? Create admin account'}
        </button>
        {error ? <div style={{ color: 'var(--danger)', fontSize: 12 }}>{error}</div> : null}
      </form>
    </div>
  )
}
