import { useEffect, useState } from 'react'
import { MismatchSampleRows } from './MismatchSampleRows'
import './ValidationPanel.css'

const apiBase = import.meta.env.VITE_API_BASE ?? ''
const pollTimeoutRaw = Number(import.meta.env.VITE_VALIDATION_POLL_TIMEOUT_MS ?? 0)
const pollTimeoutMs = Number.isFinite(pollTimeoutRaw) ? pollTimeoutRaw : 0

function absoluteApiUrl(pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl
  const base = apiBase.replace(/\/$/, '')
  const path = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`
  return base ? `${base}${path}` : path
}

/** Backend returns grouped samples; table expects a flat list. */
function normalizeValidateResult(data) {
  if (!data || data.mismatch_samples?.length || !data.mismatch_sample_groups) return data
  const g = data.mismatch_sample_groups
  return {
    ...data,
    mismatch_samples: [
      ...(g.missing_in_target ?? []),
      ...(g.extra_in_target ?? []),
      ...(g.value_mismatch ?? []),
    ],
  }
}

async function pollValidationJob(
  pollPath,
  { timeoutMs = 0, intervalMs = 400, onPoll } = {},
) {
  const url = absoluteApiUrl(pollPath)
  const deadline = timeoutMs > 0 ? Date.now() + timeoutMs : Number.POSITIVE_INFINITY
  while (Date.now() < deadline) {
    const res = await fetch(url, { method: 'GET' })
    const raw = await res.text()
    let payload = {}
    if (raw) {
      try {
        payload = JSON.parse(raw)
      } catch {
        throw new Error(raw.trim().slice(0, 400) || `Non-JSON poll response (${res.status})`)
      }
    }
    if (!res.ok) {
      throw new Error(formatDetail(payload.detail) || `${res.status} ${res.statusText}`)
    }
    const st = payload.status
    if (typeof onPoll === 'function') onPoll(payload)
    if (st === 'completed' && payload.result) return normalizeValidateResult(payload.result)
    if (st === 'failed') throw new Error(payload.error || 'Validation job failed')
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  throw new Error('Timed out waiting for validation job to finish')
}

/** Human-readable lines for the running panel (async job UX). */
function jobRunningCopy(phase, jobId) {
  const idLine = jobId ? (
    <span className="validation-job-id">
      Job id: <code>{jobId}</code>
    </span>
  ) : null
  if (typeof phase === 'string' && phase.startsWith('duckdb_')) {
    const pretty = {
      duckdb_init: 'Initializing DuckDB',
      duckdb_load_source: 'Loading source CSV',
      duckdb_load_target: 'Loading target CSV',
      duckdb_loaded: 'CSV load complete',
      duckdb_checks: 'Validating UID constraints',
      duckdb_missing: 'Scanning rows missing in target',
      duckdb_extra: 'Scanning extra rows in target',
      duckdb_value_prepare: 'Preparing value mismatch join',
      duckdb_value_extract: 'Extracting value mismatches',
      duckdb_export: 'Writing mismatch artifact',
      duckdb_finalize: 'Finalizing result',
      duckdb_done: 'DuckDB reconciliation complete',
    }
    return {
      title: pretty[phase] ?? 'DuckDB reconciliation',
      body: (
        <>
          Processing server-side comparison with external-memory DuckDB pipeline.
          {idLine ? <> {idLine}</> : null}
        </>
      ),
      extra: null,
    }
  }

  switch (phase) {
    case 'upload':
    case 'uploading':
      return {
        title: 'Uploading files…',
        body: <>Sending CSVs to the API. The next step returns HTTP 202 and starts a background worker.</>,
        extra: null,
      }
    case 'accepted':
      return {
        title: 'Job accepted',
        body: (
          <>
            The server responded with <strong>202 Accepted</strong> — validation does not run inside this request.
            {idLine ? <> {idLine}</> : null}
          </>
        ),
        extra: 'Polling for status until the worker finishes…',
      }
    case 'queued':
      return {
        title: 'Job queued',
        body: (
          <>
            Your job is in the queue and will start shortly.
            {idLine ? <> {idLine}</> : null}
          </>
        ),
        extra: 'Large files can take several minutes — you can keep this tab open.',
      }
    case 'running':
      return {
        title: 'Validation running',
        body: (
          <>
            A background worker is comparing the two files on the server (streaming / external memory).
            {idLine ? <> {idLine}</> : null}
          </>
        ),
        extra: 'Still working…',
      }
    default:
      return {
        title: 'Working…',
        body: <>Please wait.</>,
        extra: null,
      }
  }
}

function formatBytes(n) {
  if (!Number.isFinite(n) || n <= 0) return '0 B'
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let i = 0
  let v = n
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function formatPercent(n) {
  if (!Number.isFinite(n)) return null
  return `${Math.max(0, Math.min(100, Number(n))).toFixed(1)}%`
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

export function ValidationPanel() {
  const [sourceFile, setSourceFile] = useState(null)
  const [targetFile, setTargetFile] = useState(null)
  const [useLocalPaths, setUseLocalPaths] = useState(false)
  const [sourcePath, setSourcePath] = useState('')
  const [targetPath, setTargetPath] = useState('')
  const [uidColumn, setUidColumn] = useState('id')
  const [delimiter, setDelimiter] = useState('auto')
  const [phase, setPhase] = useState('idle')
  const [elapsedMs, setElapsedMs] = useState(0)
  const [result, setResult] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  /** Sub-state while phase === 'running': async job progress for clearer UX. */
  const [jobProgress, setJobProgress] = useState({
    phase: 'upload',
    jobId: null,
    message: '',
    progress: {},
  })

  const running = phase === 'running'

  useEffect(() => {
    if (!running) return
    const t0 = performance.now()
    const id = setInterval(() => {
      setElapsedMs(Math.round(performance.now() - t0))
    }, 100)
    return () => clearInterval(id)
  }, [running])

  const jobUi = running ? jobRunningCopy(jobProgress.phase, jobProgress.jobId) : null

  async function handleSubmit(e) {
    e.preventDefault()
    if (useLocalPaths) {
      if (!sourcePath.trim() || !targetPath.trim()) return
    } else if (!sourceFile || !targetFile) {
      return
    }

    setPhase('running')
    setElapsedMs(0)
    setResult(null)
    setErrorMessage('')
    setJobProgress({ phase: 'upload', jobId: null, message: '', progress: {} })

    const postUrl = absoluteApiUrl(useLocalPaths ? '/api/v1/validate/local' : '/api/v1/validate')

    try {
      let res
      if (useLocalPaths) {
        res = await fetch(postUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_path: sourcePath.trim(),
            target_path: targetPath.trim(),
            uid_column: uidColumn.trim(),
            delimiter: delimiter.trim() || 'auto',
          }),
        })
      } else {
        const body = new FormData()
        body.append('source_file', sourceFile)
        body.append('target_file', targetFile)
        body.append('uid_column', uidColumn.trim())
        body.append('delimiter', delimiter.trim() || 'auto')
        res = await fetch(postUrl, {
          method: 'POST',
          body,
        })
      }

      const raw = await res.text()
      let data = {}
      if (raw) {
        try {
          data = JSON.parse(raw)
        } catch {
          data = { detail: raw.trim().slice(0, 800) || `Non-JSON response (${res.status})` }
        }
      }

      if (!res.ok) {
        const msg = formatDetail(data.detail) || raw?.trim()?.slice(0, 800) || ''
        throw new Error(msg || `${res.status} ${res.statusText}`)
      }

      let final = data
      if (res.status === 202 && data.poll_url) {
        const jid = data.job_id != null ? String(data.job_id) : null
        setJobProgress({ phase: 'accepted', jobId: jid, message: '', progress: {} })
        final = await pollValidationJob(data.poll_url, {
          timeoutMs: pollTimeoutMs,
          onPoll: (payload) => {
            const st = payload?.status
            const phase = payload?.phase || (st === 'running' ? 'running' : st) || 'running'
            setJobProgress((p) => ({
              ...p,
              phase,
              message: typeof payload?.message === 'string' ? payload.message : '',
              progress: payload?.progress && typeof payload.progress === 'object' ? payload.progress : {},
            }))
          },
        })
      } else if (data.summary) {
        final = normalizeValidateResult(data)
      } else {
        throw new Error('Unexpected API response: expected 202 + poll_url or legacy summary payload')
      }

      setResult(final)
      setPhase('success')
    } catch (err) {
      setPhase('error')
      setErrorMessage(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div className="validation-panel">
      <form className="validation-form" onSubmit={handleSubmit}>
        <label className="validation-field">
          <span className="validation-label">Input mode</span>
          <select
            value={useLocalPaths ? 'local' : 'upload'}
            disabled={running}
            onChange={(ev) => setUseLocalPaths(ev.target.value === 'local')}
          >
            <option value="upload">Upload files from browser</option>
            <option value="local">Use server local file paths (skip upload)</option>
          </select>
          <span className="validation-field-help">
            For multi-GB files already on the API host, use local paths to avoid browser upload time.
          </span>
        </label>

        {useLocalPaths ? (
          <>
            <label className="validation-field">
              <span className="validation-label">Source path on server</span>
              <input
                type="text"
                value={sourcePath}
                disabled={running}
                onChange={(ev) => setSourcePath(ev.target.value)}
                placeholder="/data/source.csv"
              />
            </label>

            <label className="validation-field">
              <span className="validation-label">Target path on server</span>
              <input
                type="text"
                value={targetPath}
                disabled={running}
                onChange={(ev) => setTargetPath(ev.target.value)}
                placeholder="/data/target.csv"
              />
            </label>
          </>
        ) : null}

        <label className="validation-field">
          <span className="validation-label">Source CSV (expected)</span>
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={running || useLocalPaths}
            onChange={(ev) => setSourceFile(ev.target.files?.[0] ?? null)}
          />
          {sourceFile ? (
            <span className="validation-file-name">{sourceFile.name}</span>
          ) : null}
        </label>

        <label className="validation-field">
          <span className="validation-label">Target CSV (actual)</span>
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={running || useLocalPaths}
            onChange={(ev) => setTargetFile(ev.target.files?.[0] ?? null)}
          />
          {targetFile ? (
            <span className="validation-file-name">{targetFile.name}</span>
          ) : null}
        </label>

        <div className="validation-row">
          <label className="validation-field validation-field-grow">
            <span className="validation-label">UID column</span>
            <input
              type="text"
              value={uidColumn}
              disabled={running}
              onChange={(ev) => setUidColumn(ev.target.value)}
              autoComplete="off"
              placeholder="e.g. id"
            />
          </label>
          <label className="validation-field validation-field-narrow">
            <span className="validation-label">Delimiter</span>
            <input
              type="text"
              value={delimiter}
              disabled={running}
              onChange={(ev) => setDelimiter(ev.target.value)}
              className="validation-delimiter"
              title="Use auto, tab, \\t, single-char (, ; |), or multi-char (||, ::)"
              aria-label="CSV delimiter or auto"
              placeholder="auto"
            />
            <span className="validation-field-help">
              Recommended: <code>auto</code>. You can also use <code>tab</code>,{' '}
              <code>\t</code>, <code>|</code>, <code>||</code>, <code>::</code>.
            </span>
          </label>
        </div>

        <button
          type="submit"
          className="validation-submit"
          disabled={
            running ||
            !uidColumn.trim() ||
            (useLocalPaths
              ? !sourcePath.trim() || !targetPath.trim()
              : !sourceFile || !targetFile)
          }
        >
          {running ? (
            <>
              <span className="validation-spinner" aria-hidden />
              Running…
            </>
          ) : (
            'Run validation'
          )}
        </button>
      </form>

      <div className="validation-status" role="status" aria-live="polite">
        {running && jobUi ? (
          <div className="validation-status-running">
            <p className="validation-job-badge" aria-hidden="true">
              Async job · 202 Accepted
            </p>
            <p className="validation-status-title">{jobUi.title}</p>
            <p className="validation-status-detail">{jobUi.body}</p>
            {jobProgress.message ? <p className="validation-status-extra">{jobProgress.message}</p> : null}
            {jobProgress.progress?.percent != null ? (
              <p className="validation-status-extra">
                Progress: <strong>{formatPercent(jobProgress.progress.percent)}</strong>
              </p>
            ) : null}
            {jobProgress.progress?.total_mismatch_records != null ? (
              <p className="validation-status-extra">
                Mismatches emitted so far: <strong>{Number(jobProgress.progress.total_mismatch_records)}</strong>
              </p>
            ) : null}
            {jobProgress.progress?.value_mismatch_done != null ? (
              <p className="validation-status-extra">
                Value mismatch rows emitted: <strong>{Number(jobProgress.progress.value_mismatch_done)}</strong>
                {jobProgress.progress?.value_mismatch_total_estimate != null ? (
                  <>
                    {' '}
                    / est{' '}
                    <strong>{Number(jobProgress.progress.value_mismatch_total_estimate)}</strong>
                  </>
                ) : null}
              </p>
            ) : null}
            {jobProgress.phase === 'uploading' ? (
              <p className="validation-status-extra">
                Uploaded source: {formatBytes(Number(jobProgress.progress?.source_uploaded_bytes || 0))} | target:{' '}
                {formatBytes(Number(jobProgress.progress?.target_uploaded_bytes || 0))}
              </p>
            ) : null}
            {jobUi.extra ? <p className="validation-status-extra">{jobUi.extra}</p> : null}
            <p className="validation-status-elapsed">
              <strong>{(elapsedMs / 1000).toFixed(1)}s</strong> elapsed
            </p>
          </div>
        ) : null}

        {/* {phase === 'idle' ? (
          <p className="validation-status-hint">
            Start the API on port <code>8000</code> and use{' '}
            <code>npm run dev</code> so requests proxy to <code>/api</code>. For
            very large files already on server disk, switch to{' '}
            <strong>Use server local file paths</strong> to skip uploads.
          </p>
        ) : null} */}     



        {phase === 'success' && result ? (
          <div className="validation-result validation-result-success">
            <p className="validation-status-title">Finished</p>
            <div className="validation-summary-grid">
              <div>
                <span className="validation-metric-label">Match</span>
                <span className="validation-metric-value">
                  {result.summary?.is_match ? 'Yes' : 'No'}
                </span>
              </div>
              <div>
                <span className="validation-metric-label">Source rows</span>
                <span className="validation-metric-value">
                  {result.summary?.source_row_count ?? '—'}
                </span>
              </div>
              <div>
                <span className="validation-metric-label">Target rows</span>
                <span className="validation-metric-value">
                  {result.summary?.target_row_count ?? '—'}
                </span>
              </div>
              <div>
                <span className="validation-metric-label">Mismatch records</span>
                <span className="validation-metric-value">
                  {result.summary?.total_mismatch_records ?? '—'}
                </span>
              </div>
            </div>
            <p className="validation-counts-title">Mismatch counts</p>
            <ul className="validation-counts">
              <li>
                Missing in target:{' '}
                <strong>{result.mismatch_counts?.missing_in_target ?? 0}</strong>
              </li>
              <li>
                Extra in target:{' '}
                <strong>{result.mismatch_counts?.extra_in_target ?? 0}</strong>
              </li>
              <li>
                Value mismatch:{' '}
                <strong>{result.mismatch_counts?.value_mismatch ?? 0}</strong>
              </li>
            </ul>
            {result.run_id ? (
              <p className="validation-run-id">
                Run id: <code>{result.run_id}</code>
              </p>
            ) : null}
            {result.mismatch_samples?.length ? (
              <>
                <p className="validation-samples-title">Sample mismatches</p>
                <div className="validation-table-wrap">
                  <table className="validation-table">
                    <thead>
                      <tr>
                        <th>UID</th>
                        <th>Type</th>
                        <th>Column</th>
                        <th>
                          Expected
                          <span className="validation-th-hint"> (source)</span>
                        </th>
                        <th>
                          Actual
                          <span className="validation-th-hint"> (target)</span>
                        </th>
                      </tr>
                    </thead>
                    <MismatchSampleRows samples={result.mismatch_samples} />
                  </table>
                </div>
              </>
            ) : null}
          </div>
        ) : null}

        {phase === 'error' ? (
          <div className="validation-result validation-result-error">
            <p className="validation-status-title">Something went wrong</p>
            <p className="validation-error-detail">{errorMessage}</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}