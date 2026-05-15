import { useCallback, useState } from 'react'
import { FolderOutlined, FileOutlined, ArrowUpOutlined, FolderOpenOutlined, LoadingOutlined } from '@ant-design/icons'

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
    <div className="rounded-2xl border border-[#E8E8E8] bg-gradient-to-br from-[#FFFDEF] via-white to-[#FFF7F7] p-6 shadow-sm transition-shadow duration-300 hover:shadow-md">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <FolderOpenOutlined className="text-xl text-[#EB4C4C]" />
            <span className="text-base font-bold text-slate-800">{label}</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Browse folders in a tile view. Click folders to open them and files to select them.
          </p>
        </div>
        {value ? (
          <code
            className="max-w-full truncate rounded-lg border border-[#E8E8E8] bg-white px-3 py-1.5 font-mono text-xs text-slate-600 shadow-sm"
            title={value}
          >
            {value}
          </code>
        ) : (
          <span className="text-xs italic text-slate-400">No file selected</span>
        )}
      </div>

      <div className="flex flex-col gap-4 xl:flex-row xl:items-start">
        <div className="w-full xl:w-80 xl:flex-shrink-0">
          <div className="rounded-2xl border border-[#E8E8E8] bg-white/90 p-4 shadow-sm">
            <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Folder path
            </label>
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
              className="w-full rounded-xl border-2 border-[#E8E8E8] bg-white px-4 py-3 font-mono text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-[#EB4C4C] focus:ring-2 focus:ring-[#EB4C4C]/20 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:opacity-60"
            />
            <button
              type="button"
              disabled={disabled || loading}
              onClick={handleOpenFolder}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#EB4C4C] to-[#d83e3e] px-5 py-3 text-sm font-semibold text-[#FFFDEF] transition-all duration-200 hover:from-[#d83e3e] hover:to-[#c23030] hover:shadow-lg active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60 disabled:shadow-none"
            >
              {loading ? (
                <>
                  <LoadingOutlined className="animate-spin" />
                  <span>Loading…</span>
                </>
              ) : (
                <>
                  <FolderOpenOutlined />
                  <span>Open folder</span>
                </>
              )}
            </button>

            {error ? (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                <p className="font-semibold">Error</p>
                <p className="mt-1">{error}</p>
              </div>
            ) : null}
          </div>
        </div>

        {hasListed ? (
          <div className="min-w-0 flex-1">
            <div className="rounded-2xl border border-[#E8E8E8] bg-white/90 p-4 shadow-sm">
              <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                <FolderOutlined className="flex-shrink-0 text-slate-400" />
                <code className="min-w-0 flex-1 truncate font-mono text-[11px] text-slate-700">
                  {listedDir ?? (loading ? 'Loading…' : '—')}
                </code>
                <span className="rounded-full bg-slate-100 px-2 py-1 font-semibold text-slate-500">
                  {entries.length} items
                </span>
                {parentPath ? (
                  <button
                    type="button"
                    disabled={disabled || loading}
                    onClick={handleGoUp}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 transition-all hover:border-[#EB4C4C] hover:text-[#EB4C4C] disabled:opacity-50"
                  >
                    <ArrowUpOutlined className="text-xs" />
                    <span>Up</span>
                  </button>
                ) : null}
              </div>

              {truncated ? (
                <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  Listing truncated - only the first 5000 entries are shown.
                </div>
              ) : null}

              <div className="max-h-[34rem] overflow-y-auto rounded-2xl border border-[#E8E8E8] bg-[#FCFCFC] p-3">
                {!loading && entries.length === 0 ? (
                  <div className="flex min-h-52 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-white text-center text-sm text-slate-400">
                    Empty folder
                  </div>
                ) : null}

                {loading && entries.length === 0 ? (
                  <div className="flex min-h-52 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-white text-sm text-slate-400">
                    <span className="flex items-center gap-2">
                      <LoadingOutlined className="animate-spin text-[#EB4C4C]" />
                      Loading…
                    </span>
                  </div>
                ) : null}

                {entries.length > 0 ? (
                  <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4">
                    {entries.map((e) => {
                      const selected = !e.is_dir && e.path === value
                      return (
                        <button
                          key={e.path}
                          type="button"
                          disabled={disabled}
                          onClick={() => handleEntryClick(e)}
                          className={`group flex min-h-48 flex-col items-center justify-start rounded-2xl border p-4 text-center transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${
                            selected
                              ? 'border-[#EB4C4C] bg-[#EB4C4C]/10 shadow-md shadow-[#EB4C4C]/10'
                              : 'border-[#E8E8E8] bg-white hover:-translate-y-0.5 hover:border-[#EB4C4C]/40 hover:shadow-md'
                          }`}
                        >
                          <div
                            className={`mb-3 flex h-24 w-24 items-center justify-center rounded-2xl border transition-all duration-200 ${
                              e.is_dir
                                ? 'border-blue-100 bg-blue-50 text-blue-500 group-hover:bg-blue-100 group-hover:text-blue-600'
                                : 'border-slate-200 bg-slate-50 text-slate-500 group-hover:bg-slate-100 group-hover:text-slate-700'
                            } ${selected ? 'scale-105' : ''}`}
                          >
                            {e.is_dir ? <FolderOutlined className="text-4xl" /> : <FileOutlined className="text-4xl" />}
                          </div>

                          <span
                            className={`w-full whitespace-normal break-words px-2 font-mono text-sm font-medium leading-snug transition-colors ${
                              selected ? 'text-slate-900' : 'text-slate-700 group-hover:text-slate-900'
                            }`}
                            title={e.name}
                          >
                            {e.name}
                          </span>

                          <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">
                            {e.is_dir ? 'Folder' : 'File'}
                          </span>

                          {selected ? (
                            <span className="mt-2 rounded-full bg-[#EB4C4C] px-2 py-0.5 text-[10px] font-semibold text-[#FFFDEF]">
                              Selected
                            </span>
                          ) : null}
                        </button>
                      )
                    })}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
