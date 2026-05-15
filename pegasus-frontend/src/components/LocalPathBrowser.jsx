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
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (typeof e === 'object' && e != null ? e.msg ?? e.message : null) ?? JSON.stringify(e))
      .join('; ')
  }
  return JSON.stringify(detail)
}

function parentDirOfFile(filePath) {
  const trimmed = (filePath || '').trim()
  if (!trimmed) return ''
  const lastSlash = trimmed.lastIndexOf('/')
  if (lastSlash <= 0) return ''
  return trimmed.slice(0, lastSlash) || ''
}

/**
 * Pick a server-side CSV: enter a folder path, list its contents, then click a file.
 */
export default function LocalPathBrowser({ label, value, onChange, disabled }) {
  const [folderInput, setFolderInput] = useState(() => parentDirOfFile(value))
  const [listedDir, setListedDir] = useState(null)
  const [parentPath, setParentPath] = useState(null)
  const [entries, setEntries] = useState([])
  const [truncated, setTruncated] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hasListed, setHasListed] = useState(false)

  const loadDirectory = useCallback(async (dirPath) => {
    setLoading(true)
    setError('')
    try {
      const q = new URLSearchParams({ path: dirPath })
      const res = await fetch(`${absoluteApiUrl('/api/v1/validate/local/browse')}?${q}`)
      const payload = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(formatDetail(payload.detail) || `${res.status} ${res.statusText}`)
      }
      const resolved = payload.path ?? dirPath
      setListedDir(resolved)
      setFolderInput(resolved)
      setParentPath(payload.parent_path ?? null)
      setEntries(Array.isArray(payload.entries) ? payload.entries : [])
      setTruncated(Boolean(payload.truncated))
      setHasListed(true)
    } catch (e) {
      setError(e.message || 'Browse failed')
      setEntries([])
      setListedDir(null)
      setParentPath(null)
      setTruncated(false)
    } finally {
      setLoading(false)
    }
  }, [])

  function handleOpenFolder() {
    const p = folderInput.trim()
    if (!p) {
      setError('Enter an absolute folder path on the server')
      return
    }
    loadDirectory(p)
  }

  function handleGoUp() {
    if (parentPath) loadDirectory(parentPath)
  }

  function handleEntryClick(entry) {
    if (entry.is_dir) {
      loadDirectory(entry.path)
      return
    }
    onChange(entry.path)
  }

  return (
    <div className="rounded-xl border border-[#F1F1F1] bg-[#FFFDEF]/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <span className="text-sm font-semibold text-slate-700">{label}</span>
        {value ? (
          <code className="max-w-full truncate rounded bg-white px-2 py-1 text-[11px] text-slate-600" title={value}>
            {value}
          </code>
        ) : (
          <span className="text-xs text-slate-500">No file selected</span>
        )}
      </div>

      <p className="text-xs text-slate-500 mb-3">
        Enter a folder path on the server, open it, then click a file to select it. Use Up or open subfolders to
        navigate.
      </p>

      <div className="flex gap-4">
        {/* Left Column: Input and Controls */}
        <div className="flex flex-col gap-2 flex-shrink-0 w-full sm:w-auto">
          <div className="flex flex-col gap-2">
            <input
              type="text"
              value={folderInput}
              disabled={disabled}
              onChange={(ev) => setFolderInput(ev.target.value)}
              onKeyDown={(ev) => {
                if (ev.key === 'Enter') {
                  ev.preventDefault()
                  handleOpenFolder()
                }
              }}
              placeholder="/home/ansh.raj/Pegasus/test-data"
              className="rounded-lg border border-[#F1F1F1] bg-white px-3 py-2 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-[#EB4C4C] focus:ring-2 focus:ring-[#EB4C4C]/20 disabled:cursor-not-allowed disabled:opacity-60 w-full sm:w-64"
            />
            <button
              type="button"
              disabled={disabled || loading}
              onClick={handleOpenFolder}
              className="rounded-lg bg-[#EB4C4C] px-4 py-2 text-sm font-semibold text-[#FFFDEF] hover:bg-[#d83e3e] disabled:cursor-not-allowed disabled:opacity-60 w-full"
            >
              {loading ? 'Loading…' : 'Open folder'}
            </button>
          </div>

          {error ? <p className="text-xs text-red-600">{error}</p> : null}
        </div>

        {/* Right Column: File Listing */}
        {hasListed ? (
          <div className="flex-1 min-w-0 flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
              <span className="font-medium">Contents of:</span>
              <code className="break-all rounded bg-white px-1.5 py-0.5 text-[11px] truncate">
                {listedDir ?? (loading ? '…' : '—')}
              </code>
              {parentPath ? (
                <button
                  type="button"
                  disabled={disabled || loading}
                  onClick={handleGoUp}
                  className="rounded border border-slate-300 bg-white px-2 py-0.5 text-xs font-medium text-slate-700 hover:border-[#EB4C4C] disabled:opacity-50"
                >
                  Up
                </button>
              ) : null}
            </div>
            {truncated ? (
              <p className="text-xs text-amber-700">Listing truncated — only the first 5000 entries are shown.</p>
            ) : null}
            <ul className="max-h-96 overflow-y-auto rounded-lg border border-[#F1F1F1] bg-white text-sm flex-1">
              {loading && entries.length === 0 ? (
                <li className="px-3 py-2 text-slate-500">Loading…</li>
              ) : null}
              {!loading && entries.length === 0 ? (
                <li className="px-3 py-2 text-slate-500">Empty folder</li>
              ) : null}
              {entries.map((e) => {
                const selected = !e.is_dir && e.path === value
                return (
                  <li key={e.path}>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => handleEntryClick(e)}
                      className={`flex w-full items-center gap-2 px-3 py-2 text-left disabled:cursor-not-allowed disabled:opacity-50 ${
                        selected
                          ? 'bg-[#EB4C4C]/10 text-slate-900'
                          : 'text-slate-700 hover:bg-[#FFFDEF]'
                      }`}
                    >
                      <span className="w-10 shrink-0 text-center text-[10px] font-semibold uppercase text-slate-400">
                        {e.is_dir ? 'dir' : 'file'}
                      </span>
                      <span className="min-w-0 flex-1 truncate font-mono text-xs">{e.name}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  )
}
