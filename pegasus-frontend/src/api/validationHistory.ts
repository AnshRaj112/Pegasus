import { absoluteApiUrl, parseJson } from './http' // wait, parseJson wasn't exported from http, let's define locally or import it.

const apiBase = (import.meta as any).env.VITE_API_BASE ?? ''

function formatDetail(detail: any): string {
  if (detail == null) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (typeof e === 'object' && e != null ? (e.msg ?? e.message) : null) ?? JSON.stringify(e))
      .join('; ')
  }
  return JSON.stringify(detail)
}

async function localParseJson(res: Response): Promise<any> {
  const raw = await res.text()
  if (!raw) return {}
  try {
    return JSON.parse(raw)
  } catch {
    return { detail: raw.trim().slice(0, 500) }
  }
}

export async function fetchValidationDailyStats({ days = 7, from, to }: { days?: number; from?: string; to?: string } = {}): Promise<any> {
  const params = new URLSearchParams()
  if (from && to) {
    params.set('from', from)
    params.set('to', to)
  } else {
    params.set('days', String(days))
  }
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history/daily-stats?${params}`)!)
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Daily stats failed (${res.status})`)
  return data
}

export async function fetchValidationHistory({
  limit = 50,
  offset = 0,
  sourcePath,
  targetPath,
}: { limit?: number; offset?: number; sourcePath?: string; targetPath?: string } = {}): Promise<any> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (sourcePath) params.set('source_path', sourcePath)
  if (targetPath) params.set('target_path', targetPath)
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history?${params}`)!)
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `History list failed (${res.status})`)
  return data
}

export async function fetchEntityInsights({ limit = 50 }: { limit?: number } = {}): Promise<any> {
  const params = new URLSearchParams({ limit: String(limit) })
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history/entities/insights?${params}`)!)
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Entity insights failed (${res.status})`)
  return data
}

export async function createEntityDefinition({ displayName, aliases = [] }: { displayName: string; aliases?: string[] }): Promise<any> {
  const res = await fetch(absoluteApiUrl('/api/v1/validate/history/entities')!, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      display_name: displayName,
      aliases,
    }),
  })
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Create entity failed (${res.status})`)
  return data
}

export async function fetchValidationHistoryDetail(runId: string): Promise<any> {
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history/${runId}`)!)
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `History detail failed (${res.status})`)
  return data
}

export async function fetchValidationHistoryMismatches(
  runId: string,
  { limit = 100, offset = 0 }: { limit?: number; offset?: number } = {}
): Promise<any> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history/${runId}/mismatches?${params}`)!)
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Mismatches failed (${res.status})`)
  return data
}

export function formatDuration(seconds: number | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return '—'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s.toFixed(0)}s`
}

export function basename(path: string | undefined): string {
  if (!path) return '—'
  const parts = String(path).split(/[/\\]/)
  return parts[parts.length - 1] || path
}

export async function deleteValidationHistoryRun(runId: string): Promise<any> {
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history/${runId}`)!, {
    method: 'DELETE',
  })
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Delete failed (${res.status})`)
  return data
}

export async function deleteValidationHistoryByPair(sourcePath: string, targetPath: string): Promise<any> {
  const params = new URLSearchParams({ source_path: sourcePath, target_path: targetPath })
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/history?${params}`)!, {
    method: 'DELETE',
  })
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Delete failed (${res.status})`)
  return data
}

export async function deleteValidationHistoryAll(): Promise<any> {
  const res = await fetch(absoluteApiUrl('/api/v1/validate/history?all=true')!, {
    method: 'DELETE',
  })
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Clear history failed (${res.status})`)
  return data
}

export async function saveValidationDraft({
  sourcePath,
  targetPath,
  uidColumn,
  delimiter = 'auto',
  columnMappings = [],
  validateHeaderFormats = false,
  validateFooters = false,
}: {
  sourcePath: string
  targetPath: string
  uidColumn: string
  delimiter?: string
  columnMappings?: any[]
  validateHeaderFormats?: boolean
  validateFooters?: boolean
}): Promise<any> {
  const res = await fetch(absoluteApiUrl('/api/v1/validate/history/draft')!, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_path: sourcePath,
      target_path: targetPath,
      uid_column: uidColumn,
      delimiter: delimiter,
      column_mappings: columnMappings,
      validate_header_formats: validateHeaderFormats,
      validate_footers: validateFooters,
    }),
  })
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Save draft failed (${res.status})`)
  return data
}

export async function fetchLocalBrowseConfig(): Promise<any> {
  const res = await fetch(absoluteApiUrl('/api/v1/validate/local/browse/config')!)
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Browse config failed (${res.status})`)
  return data
}

export async function fetchLocalColumnPreview({
  sourcePath,
  targetPath,
  uidColumn,
  delimiter = 'auto',
}: {
  sourcePath: string
  targetPath: string
  uidColumn: string
  delimiter?: string
}): Promise<any> {
  const params = new URLSearchParams({
    source_path: sourcePath.trim(),
    target_path: targetPath.trim(),
    uid_column: uidColumn.trim(),
    delimiter: delimiter.trim() || 'auto',
  })
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/local/columns?${params}`)!)
  const data = await localParseJson(res)
  if (!res.ok) throw new Error(formatDetail(data.detail) || `Column preview failed (${res.status})`)
  return data
}
