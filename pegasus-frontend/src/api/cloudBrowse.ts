const apiBase = (import.meta as any).env.VITE_API_BASE ?? ''

function absoluteApiUrl(pathOrUrl: string | undefined): string | undefined {
  if (!pathOrUrl) return pathOrUrl
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl
  const base = apiBase.replace(/\/$/, '')
  const path = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`
  return base ? `${base}${path}` : path
}

function formatDetail(detail: any): string {
  if (detail == null) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(e => (typeof e === 'object' && e != null ? (e.msg ?? e.message) : null) ?? JSON.stringify(e)).join('; ')
  return JSON.stringify(detail)
}

export async function browseCloudPrefix({
  bucket,
  prefix,
  credentialsJson,
  connectionId,
  projectId,
  fileFormat,
}: {
  bucket?: string
  prefix?: string
  credentialsJson?: string
  connectionId?: string
  projectId?: string
  fileFormat?: string
}): Promise<any> {
  const res = await fetch(absoluteApiUrl('/api/v1/validate/cloud/browse')!, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bucket: bucket?.trim() || undefined,
      prefix: prefix || '',
      credentials_json: credentialsJson || undefined,
      connection_id: connectionId || undefined,
      project_id: projectId?.trim() || undefined,
      file_format: fileFormat || 'csv',
    }),
  })
  const payload = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(formatDetail(payload.detail) || `${res.status} ${res.statusText}`)
  return payload
}

export async function matchCloudFilePairs({
  bucket,
  sourcePrefix,
  targetPrefix,
  credentialsJson,
  connectionId,
  projectId,
  fileFormat,
  recursive,
}: {
  bucket?: string
  sourcePrefix?: string
  targetPrefix?: string
  credentialsJson?: string
  connectionId?: string
  projectId?: string
  fileFormat?: string
  recursive?: boolean
}): Promise<any> {
  const res = await fetch(absoluteApiUrl('/api/v1/validate/cloud/match-pairs')!, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bucket: bucket?.trim() || undefined,
      source_prefix: sourcePrefix || '',
      target_prefix: targetPrefix || '',
      credentials_json: credentialsJson || undefined,
      connection_id: connectionId || undefined,
      project_id: projectId?.trim() || undefined,
      file_format: fileFormat || 'csv',
      recursive: Boolean(recursive),
    }),
  })
  const payload = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(formatDetail(payload.detail) || `${res.status} ${res.statusText}`)
  return payload
}
