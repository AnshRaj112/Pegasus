import.meta.env.VITE_API_BASE;

const apiBase = import.meta.env.VITE_API_BASE ?? ''

export function absoluteApiUrl(pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl
  const base = apiBase.replace(/\/$/, '')
  const path = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`
  return base ? `${base}${path}` : path
}

export function formatDetail(detail) {
  if (detail == null) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (typeof e === 'object' && e != null ? e.msg ?? e.message : null) ?? JSON.stringify(e))
      .join('; ')
  }
  return JSON.stringify(detail)
}

/**
 * Classify HTTP / network failures for user-visible messaging.
 * @returns {{ kind: 'backend_down'|'http'|'parse'|'unknown', message: string }}
 */
export function classifyHttpFailure({ error, response, rawBody }) {
  if (error && error.name === 'TypeError') {
    const msg = String(error.message || '')
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('Load failed')) {
      return {
        kind: 'backend_down',
        message:
          'Cannot reach the Pegasus API. The backend may have stopped or run out of memory. '
          + 'Check Docker with: docker compose ps && docker compose logs backend --tail 80',
      }
    }
  }
  if (response) {
    const status = response.status
    if (status === 502 || status === 503 || status === 504) {
      const hint = status === 502
        ? 'Bad Gateway — nginx could not reach the backend (it may have crashed during validation).'
        : status === 503
          ? 'Service unavailable — the backend is overloaded or restarting.'
          : 'Gateway timeout — the request took too long.'
      return {
        kind: 'backend_down',
        message: `${hint} Run: docker compose up -d backend && docker compose logs -f backend`,
      }
    }
    if (rawBody && rawBody.trim().startsWith('<')) {
      return {
        kind: 'backend_down',
        message: `Server returned HTML instead of JSON (HTTP ${status}). The API is likely down or misconfigured.`,
      }
    }
    return { kind: 'http', message: `HTTP ${status} ${response.statusText}` }
  }
  return { kind: 'unknown', message: error?.message ? String(error.message) : 'Request failed' }
}

export function messageFromHttpFailure(ctx, fallback = 'Request failed') {
  const c = classifyHttpFailure(ctx)
  return c.message || fallback
}

/**
 * fetch + JSON parse with consistent error handling.
 */
export async function fetchJson(url, init = {}) {
  let res
  let raw = ''
  try {
    res = await fetch(url, init)
    raw = await res.text()
  } catch (error) {
    throw new Error(messageFromHttpFailure({ error }))
  }
  let payload = {}
  if (raw) {
    try {
      payload = JSON.parse(raw)
    } catch {
      throw new Error(
        messageFromHttpFailure({ response: res, rawBody: raw })
          || raw.trim().slice(0, 400)
          || `Non-JSON response (${res.status})`,
      )
    }
  }
  if (!res.ok) {
    throw new Error(formatDetail(payload.detail) || messageFromHttpFailure({ response: res, rawBody: raw }))
  }
  return payload
}

export async function checkBackendHealth() {
  try {
    const payload = await fetchJson(absoluteApiUrl('/api/v1/health'), { method: 'GET' })
    return { ok: true, payload }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) }
  }
}