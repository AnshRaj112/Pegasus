/** Validation queue status from GET /api/v1/validate/queue */

import { absoluteApiUrl, fetchJson } from './http.js'

export async function fetchValidationQueue() {
  return fetchJson(absoluteApiUrl('/api/v1/validate/queue'), { method: 'GET' })
}
