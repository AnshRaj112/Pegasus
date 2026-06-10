/** Validation queue status from GET /api/v1/validate/queue */

import { fetchJson } from './http.js'

export async function fetchValidationQueue() {
  return fetchJson('/api/v1/validate/queue', { method: 'GET' })
}
