/** Poll validation jobs until completed / failed; surfaces backend-down errors clearly. */

import { absoluteApiUrl, fetchJson, messageFromHttpFailure } from './http.js'
import { formatJobError } from './formatError.js'
import { normalizeMismatchRow } from './validationHistory.js'

function flattenMismatchSampleGroups(groups) {
  if (!groups) return []
  return [
    ...(groups.missing_in_target ?? []),
    ...(groups.extra_in_target ?? []),
    ...(groups.value_mismatch ?? []),
  ]
}

function deriveMismatchCounts(data) {
  const counts = data?.mismatch_counts ?? {}
  const resolved = {
    missing_in_target: Number(counts.missing_in_target ?? 0),
    extra_in_target: Number(counts.extra_in_target ?? 0),
    value_mismatch: Number(
      counts.value_mismatch
      ?? data?.summary?.value_mismatch_records
      ?? data?.value_mismatch_records
      ?? 0,
    ),
  }
  if (
    resolved.missing_in_target > 0
    || resolved.extra_in_target > 0
    || resolved.value_mismatch > 0
  ) {
    return resolved
  }
  const groups = data?.mismatch_sample_groups
  if (groups) {
    const derived = {
      missing_in_target: groups.missing_in_target?.length ?? 0,
      extra_in_target: groups.extra_in_target?.length ?? 0,
      value_mismatch: groups.value_mismatch?.length ?? 0,
    }
    if (derived.missing_in_target + derived.extra_in_target + derived.value_mismatch > 0) {
      return derived
    }
  }
  const samples = data?.mismatch_samples ?? []
  if (samples.length > 0) {
    return {
      missing_in_target: samples.filter((row) => row.mismatch_type === 'missing_in_target').length,
      extra_in_target: samples.filter((row) => row.mismatch_type === 'extra_in_target').length,
      value_mismatch: samples.filter((row) => row.mismatch_type === 'value_mismatch').length,
    }
  }
  return counts ?? { missing_in_target: 0, extra_in_target: 0, value_mismatch: 0 }
}

function normalizeMismatchSampleGroups(groups) {
  if (!groups) return groups
  return {
    missing_in_target: (groups.missing_in_target ?? []).map(normalizeMismatchRow),
    extra_in_target: (groups.extra_in_target ?? []).map(normalizeMismatchRow),
    value_mismatch: (groups.value_mismatch ?? []).map(normalizeMismatchRow),
  }
}

export function normalizeValidateResult(data) {
  if (!data) return data
  const groups = normalizeMismatchSampleGroups(data.mismatch_sample_groups)
  const flattened = (data.mismatch_samples?.length ?? 0) > 0
    ? data.mismatch_samples.map(normalizeMismatchRow)
    : flattenMismatchSampleGroups(groups)
  const mismatch_counts = deriveMismatchCounts({
    ...data,
    mismatch_samples: flattened,
  })
  const totalFromCounts =
    Number(mismatch_counts.missing_in_target ?? 0)
    + Number(mismatch_counts.extra_in_target ?? 0)
    + Number(mismatch_counts.value_mismatch ?? 0)
  const summary = {
    ...(data.summary ?? {}),
    total_mismatch_records: Number(
      data.summary?.total_mismatch_records ?? totalFromCounts,
    ),
  }
  return {
    ...data,
    summary,
    mismatch_counts,
    mismatch_sample_groups: groups,
    ...(flattened.length > 0 ? { mismatch_samples: flattened } : {}),
  }
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
