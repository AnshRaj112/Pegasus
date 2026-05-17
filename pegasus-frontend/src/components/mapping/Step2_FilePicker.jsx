import { useCallback, useState } from 'react'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

function absoluteApiUrl(pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl
  const base = apiBase.replace(/\/$/, '')
  const path = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`
  return base ? `${base}${path}` : path
}

function formatDetail(detail) {
  if (detail == null) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(e => (typeof e === 'object' && e != null ? e.msg ?? e.message : null) ?? JSON.stringify(e)).join('; ')
  return JSON.stringify(detail)
}

function parentDirOfFile(filePath) {
  const trimmed = (filePath || '').trim()
  if (!trimmed) return ''
  const lastSlash = trimmed.lastIndexOf('/')
  if (lastSlash <= 0) return ''
  return trimmed.slice(0, lastSlash) || ''
}

const CHEVRON_SVG = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12' fill='none'%3E%3Cpath d='M3 4.5l3 3 3-3' stroke='%2371717a' stroke-width='1.3' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`

export default function Step2_FilePicker({ panelLabel, value, onSelect, onBack, disabled }) {
  const [folderInput, setFolderInput] = useState(() => parentDirOfFile(value) || '')
  const [folders, setFolders]         = useState([])
  const [files, setFiles]             = useState([])
  const [listedDir, setListedDir]     = useState(null)
  const [parentPath, setParentPath]   = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState('')
  const [selectedFile, setSelectedFile] = useState(value || null)
  const [hasListed, setHasListed]     = useState(false)

  const loadDirectory = useCallback(async (dirPath) => {
    setLoading(true); setError('')
    try {
      const q = new URLSearchParams({ path: dirPath })
      const res = await fetch(`${absoluteApiUrl('/api/v1/validate/local/browse')}?${q}`)
      const payload = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(formatDetail(payload.detail) || `${res.status} ${res.statusText}`)
      const resolved = payload.path ?? dirPath
      setListedDir(resolved); setFolderInput(resolved); setParentPath(payload.parent_path ?? null)
      const entries = Array.isArray(payload.entries) ? payload.entries : []
      setFolders(entries.filter(e => e.is_dir)); setFiles(entries.filter(e => !e.is_dir)); setHasListed(true)
    } catch (e) {
      setError(e.message || 'Browse failed'); setFolders([]); setFiles([]); setListedDir(null); setParentPath(null)
    } finally { setLoading(false) }
  }, [])

  function handleOpen() {
    const p = folderInput.trim()
    if (!p) { setError('Enter an absolute folder path'); return }
    loadDirectory(p)
  }

  return (
    <div style={{ animation: 'fade-in 0.2s ease', display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
            Step 1 of 3 — {panelLabel} file
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 4 }}>
            Select{' '}
            <span style={{ color: 'var(--accent)' }}>{panelLabel}</span>
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-3)' }}>
            Browse the server filesystem. Click a file to select it.
          </p>
        </div>
        {selectedFile && (
          <button
            onClick={() => onSelect(selectedFile)}
            disabled={disabled}
            className="btn btn-primary btn-lg"
            style={{ flexShrink: 0 }}
          >
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <path d="M2 6.5l3 3 6-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Use as {panelLabel}
          </button>
        )}
      </div>

      {/* Path input */}
      <div style={{
        display: 'flex', gap: 8, padding: '8px 10px',
        background: 'var(--surface-2)', border: '1px solid var(--border-2)', borderRadius: 9,
        alignItems: 'center',
      }}>
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ color: 'var(--text-4)', flexShrink: 0 }}>
          <path d="M1 3a1 1 0 011-1h2.5L6 3.5h7a.5.5 0 01.5.5v7a.5.5 0 01-.5.5H2a1 1 0 01-1-1V3z" stroke="currentColor" strokeWidth="1.3"/>
        </svg>
        <input
          type="text"
          value={folderInput}
          disabled={disabled}
          onChange={e => setFolderInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleOpen() } }}
          placeholder="/path/to/your/data"
          style={{
            flex: 1, background: 'transparent', border: 'none', outline: 'none',
            fontSize: 12, color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace',
          }}
        />
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          {parentPath && (
            <button
              type="button"
              disabled={disabled || loading}
              onClick={() => loadDirectory(parentPath)}
              className="btn btn-secondary"
              style={{ height: 28, padding: '0 10px', fontSize: 12 }}
              title="Go up"
            >
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                <path d="M5.5 8.5v-6M2 5L5.5 1.5 9 5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Up
            </button>
          )}
          <button
            type="button"
            disabled={disabled || loading}
            onClick={handleOpen}
            className="btn btn-primary"
            style={{ height: 28, padding: '0 12px', fontSize: 12 }}
          >
            {loading ? (
              <span style={{
                display: 'inline-block', width: 11, height: 11, borderRadius: '50%',
                border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff',
                animation: 'spin 0.7s linear infinite',
              }} />
            ) : 'Open'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '9px 12px', borderRadius: 8, fontSize: 12,
          background: 'var(--danger-muted)', border: '1px solid var(--danger-border)', color: 'var(--danger)',
        }}>
          {error}
        </div>
      )}

      {/* Two-panel browser */}
      {hasListed && (
        <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 8 }}>

          {/* Folders panel */}
          <div style={{ border: '1px solid var(--border-1)', borderRadius: 9, overflow: 'hidden' }}>
            <div style={{
              padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--surface-2)', borderBottom: '1px solid var(--border-1)',
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ color: 'var(--text-3)' }}>
                <path d="M1 2.5a.5.5 0 01.5-.5h3l1 1h5.5a.5.5 0 01.5.5v7a.5.5 0 01-.5.5h-10a.5.5 0 01-.5-.5v-8z" stroke="currentColor" strokeWidth="1.2" fill="currentColor" fillOpacity="0.08"/>
              </svg>
              <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)' }}>
                Folders
              </span>
              <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-4)', fontFamily: 'Geist Mono, monospace' }}>
                {folders.length}
              </span>
            </div>
            <div style={{ background: 'var(--surface-1)', maxHeight: 380, overflowY: 'auto' }}>
              {loading && (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
                  <span style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid var(--border-2)', borderTopColor: 'var(--accent)', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
                </div>
              )}
              {!loading && folders.length === 0 && (
                <div style={{ padding: '32px 12px', textAlign: 'center', fontSize: 12, color: 'var(--text-4)' }}>
                  No sub-folders
                </div>
              )}
              {folders.map(f => (
                <button
                  key={f.path}
                  type="button"
                  disabled={disabled}
                  onClick={() => loadDirectory(f.path)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 7,
                    width: '100%', padding: '7px 12px', textAlign: 'left',
                    background: 'transparent', border: 'none',
                    borderBottom: '1px solid var(--border-1)',
                    color: 'var(--text-2)', fontSize: 12, cursor: 'pointer',
                    fontFamily: 'inherit', transition: 'all 0.1s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface-2)'; e.currentTarget.style.color = 'var(--text-1)' }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-2)' }}
                >
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none" style={{ color: 'var(--text-3)', flexShrink: 0 }}>
                    <path d="M1 2.5a.5.5 0 01.5-.5h3.2l1 1H12a.5.5 0 01.5.5v7a.5.5 0 01-.5.5H1.5a.5.5 0 01-.5-.5V2.5z" stroke="currentColor" strokeWidth="1.2" fill="currentColor" fillOpacity="0.1"/>
                  </svg>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ marginLeft: 'auto', flexShrink: 0, color: 'var(--text-4)' }}>
                    <path d="M3 1l4 4-4 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
              ))}
            </div>
          </div>

          {/* Files panel */}
          <div style={{ border: '1px solid var(--border-1)', borderRadius: 9, overflow: 'hidden' }}>
            <div style={{
              padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--surface-2)', borderBottom: '1px solid var(--border-1)',
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ color: 'var(--text-3)' }}>
                <path d="M3 1h5l3 3v7H3V1z" stroke="currentColor" strokeWidth="1.2"/>
                <path d="M8 1v3h3" stroke="currentColor" strokeWidth="1.2"/>
              </svg>
              <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)' }}>
                Files
              </span>
              <code style={{ marginLeft: 4, fontSize: 10, color: 'var(--text-4)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {listedDir}
              </code>
              <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-4)', fontFamily: 'Geist Mono, monospace' }}>
                {files.length}
              </span>
              {selectedFile && (
                <button
                  type="button"
                  onClick={() => onSelect(selectedFile)}
                  disabled={disabled}
                  className="btn btn-primary"
                  style={{ marginLeft: 8, height: 24, padding: '0 10px', fontSize: 11 }}
                >
                  Use as {panelLabel}
                </button>
              )}
            </div>

            <div style={{ background: 'var(--surface-1)', maxHeight: 380, overflowY: 'auto', padding: 8 }}>
              {loading && (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
                  <span style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid var(--border-2)', borderTopColor: 'var(--accent)', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
                </div>
              )}
              {!loading && files.length === 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '40px 0', color: 'var(--text-4)', fontSize: 12 }}>
                  <svg width="28" height="28" viewBox="0 0 28 28" fill="none" style={{ opacity: 0.35 }}>
                    <path d="M7 4h10l7 7v13H7V4z" stroke="currentColor" strokeWidth="1.3"/>
                    <path d="M17 4v7h7" stroke="currentColor" strokeWidth="1.3"/>
                  </svg>
                  No files here
                </div>
              )}
              {files.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: 6 }}>
                  {files.map(f => {
                    const selected = selectedFile === f.path
                    const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
                    const isTabular = ['csv', 'tsv', 'txt', 'parquet', 'xlsx'].includes(ext)
                    return (
                      <button
                        key={f.path}
                        type="button"
                        disabled={disabled}
                        onClick={() => setSelectedFile(prev => prev === f.path ? null : f.path)}
                        style={{
                          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7,
                          padding: '10px 8px', borderRadius: 8, cursor: 'pointer',
                          background: selected ? 'var(--accent-muted)' : 'var(--surface-2)',
                          border: selected ? '1px solid var(--accent-border)' : '1px solid var(--border-1)',
                          transition: 'all 0.12s', fontFamily: 'inherit',
                        }}
                        onMouseEnter={e => { if (!selected) e.currentTarget.style.borderColor = 'var(--border-2)' }}
                        onMouseLeave={e => { if (!selected) e.currentTarget.style.borderColor = 'var(--border-1)' }}
                      >
                        {/* Icon */}
                        <div style={{
                          width: 32, height: 32, borderRadius: 6,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: selected ? 'var(--accent)' : isTabular ? 'var(--success-muted)' : 'var(--surface-3)',
                          color: selected ? '#fff' : isTabular ? 'var(--success)' : 'var(--text-3)',
                          flexShrink: 0,
                        }}>
                          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                            <path d="M3 1h6l4 4v8H3V1z" stroke="currentColor" strokeWidth="1.2"/>
                            <path d="M9 1v4h4" stroke="currentColor" strokeWidth="1.2"/>
                            {isTabular && <path d="M5 8h4M5 10.5h3" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>}
                          </svg>
                        </div>

                        {/* Extension badge */}
                        <span style={{
                          fontSize: 9, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase',
                          padding: '1px 5px', borderRadius: 3,
                          background: selected ? 'rgba(255,255,255,0.2)' : isTabular ? 'var(--success-muted)' : 'var(--surface-3)',
                          color: selected ? '#fff' : isTabular ? 'var(--success)' : 'var(--text-4)',
                        }}>
                          {ext || 'file'}
                        </span>

                        {/* Name */}
                        <span style={{
                          fontSize: 11, fontFamily: 'Geist Mono, monospace',
                          color: selected ? 'var(--accent)' : 'var(--text-2)',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          width: '100%', textAlign: 'center',
                        }} title={f.name}>
                          {f.name}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Back */}
      <button
        type="button"
        onClick={onBack}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          background: 'none', border: 'none', cursor: 'pointer',
          fontSize: 12, color: 'var(--text-3)', fontFamily: 'inherit',
          padding: 0, transition: 'color 0.12s',
        }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--text-1)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--text-3)'}
      >
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <path d="M9 6.5H3M5.5 4L3 6.5 5.5 9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        Back to storage selection
      </button>
    </div>
  )
}
