/** Poll validation jobs until completed / failed; surfaces backend-down errors clearly. */

import { absoluteApiUrl, fetchJson, messageFromHttpFailure } from './http'
import { formatJobError } from './formatError'

function flattenMismatchSampleGroups(groups: any): any[] {
  if (!groups) return []
  return [
    ...(groups.missing_in_target ?? []),
    ...(groups.extra_in_target ?? []),
    ...(groups.value_mismatch ?? []),
  ]
}

export function normalizeValidateResult(data: any): any {
  if (!data) return data
  if ((data.mismatch_samples?.length ?? 0) > 0) return data
  const flattened = flattenMismatchSampleGroups(data.mismatch_sample_groups)
  if (flattened.length === 0) return data
  return { ...data, mismatch_samples: flattened }
}

export function formatElapsed(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return ''
  if (seconds < 60) return `${Math.floor(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}m ${s}s`
}

/**
 * @param {string} pollPath
 */
export async function pollValidationJob(
  pollPath: string,
  { timeoutMs = 0, intervalMs = 400, onPoll }: { timeoutMs?: number; intervalMs?: number; onPoll?: (payload: any, meta: any) => void } = {}
): Promise<any> {
  const url = absoluteApiUrl(pollPath)!
  const started = Date.now()
  const deadline = timeoutMs > 0 ? started + timeoutMs : Number.POSITIVE_INFINITY
  let lastStatus = ''

  while (Date.now() < deadline) {
    let payload: any
    try {
      payload = await fetchJson(url, { method: 'GET' })
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error)
      if (lastStatus === 'running' || lastStatus === 'queued') {
        throw new Error(
          `${msg} The validation may still be running on the server, but this browser lost contact with the API.`
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
export async function pollValidationJobDetail(
  pollPath: string,
  { timeoutMs = 0, intervalMs = 400, onPoll }: { timeoutMs?: number; intervalMs?: number; onPoll?: (payload: any, meta: any) => void } = {}
): Promise<any> {
  const url = absoluteApiUrl(pollPath)!
  const started = Date.now()
  const deadline = timeoutMs > 0 ? started + timeoutMs : Number.POSITIVE_INFINITY
  let lastStatus = ''

  while (Date.now() < deadline) {
    let payload: any
    try {
      payload = await fetchJson(url, { method: 'GET' })
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error)
      if (lastStatus === 'running' || lastStatus === 'queued') {
        throw new Error(
          `${msg} The job may still be running on the server, but this browser lost contact with the API.`
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

export { messageFromHttpFailure }
