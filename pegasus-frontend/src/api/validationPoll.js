/** Poll validation jobs until completed / failed; surfaces backend-down errors clearly. */

import { absoluteApiUrl, fetchJson, messageFromHttpFailure } from './http.js'
import { formatJobError } from './formatError.js'

function flattenMismatchSampleGroups(groups) {
  if (!groups) return []
  return [
    ...(groups.missing_in_target ?? []),
    ...(groups.extra_in_target ?? []),
    ...(groups.value_mismatch ?? []),
  ]
}

export function normalizeValidateResult(data) {
  if (!data) return data
  if ((data.mismatch_samples?.length ?? 0) > 0) return data
  const flattened = flattenMismatchSampleGroups(data.mismatch_sample_groups)
  if (flattened.length === 0) return data
  return { ...data, mismatch_samples: flattened }
}

function formatElapsed(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return ''
  if (seconds < 60) return `${Math.floor(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}m ${s}s`
}

/**
 * @param {string} pollPath
 * @param {{ timeoutMs?: number, intervalMs?: number, onPoll?: (payload: object, meta: { elapsedMs: number }) => void }} opts
 */
export async function pollValidationJob(pollPath, { timeoutMs = 0, intervalMs = 400, onPoll } = {}) {
  const url = absoluteApiUrl(pollPath)
  const started = Date.now()
  const deadline = timeoutMs > 0 ? started + timeoutMs : Number.POSITIVE_INFINITY
  let lastStatus = ''

  while (Date.now() < deadline) {
    let payload
    try {
      payload = await fetchJson(url, { method: 'GET' })
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error)
      if (lastStatus === 'running' || lastStatus === 'queued') {
        throw new Error(
          `${msg} The validation may still be running on the server, but this browser lost contact with the API.`,
        )
      }
      throw error
    }

    lastStatus = String(payload.status || '')
    const elapsedMs = Date.now() - started
    if (typeof onPoll === 'function') {
      onPoll(payload, { elapsedMs, elapsedLabel: formatElapsed(elapsedMs / 1000) })
    }

    if (payload.status === 'completed' && payload.result) {
      return normalizeValidateResult(payload.result)
    }
    if (payload.status === 'failed') {
      throw new Error(formatJobError(payload.message || payload.error))
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
  throw new Error('Timed out waiting for validation job to finish')
}

/** Poll until completed; returns full job detail (batch or single). */
export async function pollValidationJobDetail(pollPath, { timeoutMs = 0, intervalMs = 400, onPoll } = {}) {
  const url = absoluteApiUrl(pollPath)
  const started = Date.now()
  const deadline = timeoutMs > 0 ? started + timeoutMs : Number.POSITIVE_INFINITY
  let lastStatus = ''

  while (Date.now() < deadline) {
    let payload
    try {
      payload = await fetchJson(url, { method: 'GET' })
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error)
      if (lastStatus === 'running' || lastStatus === 'queued') {
        throw new Error(
          `${msg} The job may still be running on the server, but this browser lost contact with the API.`,
        )
      }
      throw error
    }

    lastStatus = String(payload.status || '')
    const elapsedMs = Date.now() - started
    if (typeof onPoll === 'function') {
      onPoll(payload, { elapsedMs, elapsedLabel: formatElapsed(elapsedMs / 1000) })
    }

    if (payload.status === 'completed') {
      if (payload.batch_result) return payload
      if (payload.result) {
        return { ...payload, result: normalizeValidateResult(payload.result) }
      }
      return payload
    }
    if (payload.status === 'failed') {
      throw new Error(formatJobError(payload.message || payload.error))
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
  throw new Error('Timed out waiting for validation job')
}

export { messageFromHttpFailure, formatElapsed }
