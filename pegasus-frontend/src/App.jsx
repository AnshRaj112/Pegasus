import { ValidationPanel } from './components/ValidationPanel'
import './App.css'

function App() {
  return (
    <>
      <header className="app-header">
        <h1>Pegasus</h1>
        <p className="app-tagline">CSV validation</p>
      </header>

      <main className="app-main">
        <ValidationPanel />
      </main>

      <footer className="app-footer">
        <p>
          Dev: <code>npm run dev</code> on <code>5173</code> (proxies <code>/api</code> →{' '}
          <code>8000</code>). Production build: <code>npm run build</code> then{' '}
          <code>npm run preview</code> on <code>5173</code> — set backend{' '}
          <code>PEGASUS_CORS_ORIGINS</code> per <code>.env.production.example</code>.
        </p>
        <p>
          API: <code>uvicorn pegasus.main:app --host 0.0.0.0 --port 8000</code> from{' '}
          <code>pegasus-backend/</code>
        </p>
      </footer>
    </>
  )
}

export default App