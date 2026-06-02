import { useEffect, useState } from 'react'
import {
  createAdminCloudConnection,
  deleteAdminCloudConnection,
  listAdminCloudConnections,
} from '../api/adminCloudConnections'

const emptyForm = {
  name: '',
  bucket: '',
  project_id: '',
  credentials_json: '',
}

export default function AdminCloudConnections() {
  const [rows, setRows] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await listAdminCloudConnections()
      setRows(Array.isArray(data) ? data : [])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSaveConnection(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await createAdminCloudConnection({
        name: form.name.trim(),
        bucket: form.bucket.trim(),
        project_id: form.project_id.trim() || undefined,
        credentials_json: form.credentials_json,
        provider: 'google-cloud-storage',
        active: true,
      })
      setForm(emptyForm)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    setError('')
    try {
      await deleteAdminCloudConnection(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <section style={{ background: 'var(--surface-1)', border: '1px solid var(--border-1)', borderRadius: 10, padding: 16 }}>
        <h2 style={{ margin: 0, color: 'var(--text-1)' }}>Admin - Cloud Connections</h2>
        <p style={{ marginTop: 6, fontSize: 12, color: 'var(--text-3)' }}>
          Credentials are encrypted at rest in backend DB and never returned to the browser after save.
        </p>
      </section>

      <section style={{ background: 'var(--surface-1)', border: '1px solid var(--border-1)', borderRadius: 10, padding: 16 }}>
        <h3 style={{ marginTop: 0, color: 'var(--text-1)' }}>Add connection</h3>
        <form onSubmit={handleSaveConnection} style={{ display: 'grid', gap: 8, maxWidth: 720 }}>
          <input className="input input-mono" placeholder="Connection name" value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
          <input className="input input-mono" placeholder="Bucket" value={form.bucket} onChange={(e) => setForm((p) => ({ ...p, bucket: e.target.value }))} />
          <input className="input input-mono" placeholder="Project ID (optional)" value={form.project_id} onChange={(e) => setForm((p) => ({ ...p, project_id: e.target.value }))} />
          <textarea className="input input-mono" rows={8} placeholder="Service account JSON" value={form.credentials_json} onChange={(e) => setForm((p) => ({ ...p, credentials_json: e.target.value }))} />
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving...' : 'Save encrypted connection'}
          </button>
        </form>
      </section>

      <section style={{ background: 'var(--surface-1)', border: '1px solid var(--border-1)', borderRadius: 10, padding: 16 }}>
        <h3 style={{ marginTop: 0, color: 'var(--text-1)' }}>Saved connections</h3>
        {loading ? <p style={{ color: 'var(--text-3)' }}>Loading...</p> : null}
        {!loading && rows.length === 0 ? <p style={{ color: 'var(--text-3)' }}>No saved connections.</p> : null}
        <div style={{ display: 'grid', gap: 8 }}>
          {rows.map((row) => (
            <div key={row.id} style={{ border: '1px solid var(--border-1)', borderRadius: 8, padding: 10, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ color: 'var(--text-1)', fontWeight: 600 }}>{row.name}</div>
                <div style={{ color: 'var(--text-3)', fontSize: 12 }}>gs://{row.bucket} {row.project_id ? `· ${row.project_id}` : ''}</div>
              </div>
              <button type="button" className="btn btn-ghost" onClick={() => handleDelete(row.id)}>Delete</button>
            </div>
          ))}
        </div>
        {error ? <p style={{ color: 'var(--danger)', marginTop: 8 }}>{error}</p> : null}
      </section>
    </div>
  )
}
