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

async function parseJson(res) {
  const raw = await res.text()
  if (!raw) return {}
  try {
    return JSON.parse(raw)
  } catch {
    return { detail: raw.trim().slice(0, 500) }
  }
}

export async function fetchValidationHistory({ limit = 50, offset = 0, sourcePath, targetPath } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (sourcePath) params.set('source_path', sourcePath)
  if (targetPath) params.set('target_path', targetPath)
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history?${params}`))
  const data = await parseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `History list failed (${res.status})`)
  return data
}

export async function fetchValidationHistoryDetail(runId) {
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history/${runId}`))
  const data = await parseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `History detail failed (${res.status})`)
  return data
}

export async function fetchValidationHistoryMismatches(runId, { limit = 100, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history/${runId}/mismatches?${params}`))
  const data = await parseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Mismatches failed (${res.status})`)
  return data
}

export function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return '—'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s.toFixed(0)}s`
}

export function basename(path) {
  if (!path) return '—'
  const parts = String(path).split(/[/\\]/)
  return parts[parts.length - 1] || path
}

export async function deleteValidationHistoryRun(runId) {
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history/${runId}`), {
    method: 'DELETE',
  })
  const data = await parseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Delete failed (${res.status})`)
  return data
}

export async function deleteValidationHistoryByPair(sourcePath, targetPath) {
  const params = new URLSearchParams({ source_path: sourcePath, target_path: targetPath })
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history?${params}`), {
    method: 'DELETE',
  })
  const data = await parseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Delete failed (${res.status})`)
  return data
}

export async function deleteValidationHistoryAll() {
  const res = await fetch(absoluteApiUrl('/api/v1/validate/history?all=true'), {
    method: 'DELETE',
  })
  const data = await parseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Clear history failed (${res.status})`)
  return data
}


