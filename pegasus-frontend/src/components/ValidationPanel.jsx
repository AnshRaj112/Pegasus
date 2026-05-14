import { useEffect, useState } from 'react'
import { MismatchSampleRows } from './MismatchSampleRows'
import { useNavigate } from 'react-router-dom';

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
    <span className="mt-2 block text-sm text-slate-600">
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
  const navigate = useNavigate();
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
    <div className="space-y-8">
      <section className="rounded-2xl border border-[#F1F1F1] border-l-4 border-l-[#EB4C4C] bg-white p-6 shadow-[0_12px_40px_rgba(235,76,76,0.10)] sm:p-8">
        <p className="mb-5 text-center text-sm font-medium text-slate-600 sm:text-base">
          Upload files or use server-local paths to run CSV comparison.
        </p>

        <form className="space-y-5" onSubmit={handleSubmit}>
          <label className="block space-y-2">
            <span className="text-sm font-semibold text-slate-700">Input mode</span>
            <select
              value={useLocalPaths ? 'local' : 'upload'}
              disabled={running}
              onChange={(ev) => setUseLocalPaths(ev.target.value === 'local')}
              className="w-full rounded-lg border border-[#F1F1F1] bg-[#FFFDEF] px-3 py-2.5 text-sm text-slate-700 outline-none transition focus:border-[#EB4C4C] focus:ring-2 focus:ring-[#EB4C4C]/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <option value="upload">Upload files from browser</option>
              <option value="local">Use server local file paths (skip upload)</option>
            </select>
            <span className="block text-xs text-slate-500">
              For multi-GB files already on the API host, use local paths to avoid browser upload time.
            </span>
          </label>

          {useLocalPaths ? (
            <>
              <label className="block space-y-2">
                <span className="text-sm font-semibold text-slate-700">Source path on server</span>
                <input
                  type="text"
                  value={sourcePath}
                  disabled={running}
                  onChange={(ev) => setSourcePath(ev.target.value)}
                  placeholder="/data/source.csv"
                  className="w-full rounded-lg border border-[#F1F1F1] bg-white px-3 py-2.5 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-[#EB4C4C] focus:ring-2 focus:ring-[#EB4C4C]/20 disabled:cursor-not-allowed disabled:opacity-60"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-semibold text-slate-700">Target path on server</span>
                <input
                  type="text"
                  value={targetPath}
                  disabled={running}
                  onChange={(ev) => setTargetPath(ev.target.value)}
                  placeholder="/data/target.csv"
                  className="w-full rounded-lg border border-[#F1F1F1] bg-white px-3 py-2.5 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-[#EB4C4C] focus:ring-2 focus:ring-[#EB4C4C]/20 disabled:cursor-not-allowed disabled:opacity-60"
                />
              </label>
            </>
          ) : null}

          <label className="block space-y-2">
            <span className="text-sm font-semibold text-slate-700">Source CSV (expected)</span>
            <input
              type="file"
              accept=".csv,text/csv"
              disabled={running || useLocalPaths}
              onChange={(ev) => setSourceFile(ev.target.files?.[0] ?? null)}
              className="w-full rounded-lg border border-[#F1F1F1] bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-[#EB4C4C] file:px-3 file:py-2 file:text-sm file:font-semibold file:text-[#FFFDEF] hover:file:bg-[#d83e3e] disabled:cursor-not-allowed disabled:opacity-60"
            />
            {sourceFile ? <span className="block text-xs text-slate-600">{sourceFile.name}</span> : null}
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-semibold text-slate-700">Target CSV (actual)</span>
            <input
              type="file"
              accept=".csv,text/csv"
              disabled={running || useLocalPaths}
              onChange={(ev) => setTargetFile(ev.target.files?.[0] ?? null)}
              className="w-full rounded-lg border border-[#F1F1F1] bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-[#EB4C4C] file:px-3 file:py-2 file:text-sm file:font-semibold file:text-[#FFFDEF] hover:file:bg-[#d83e3e] disabled:cursor-not-allowed disabled:opacity-60"
            />
            {targetFile ? <span className="block text-xs text-slate-600">{targetFile.name}</span> : null}
          </label>

          <div className="grid gap-4 md:grid-cols-[1fr_240px]">
            <label className="block space-y-2">
              <span className="text-sm font-semibold text-slate-700">UID column</span>
              <input
                type="text"
                value={uidColumn}
                disabled={running}
                onChange={(ev) => setUidColumn(ev.target.value)}
                autoComplete="off"
                placeholder="e.g. id"
                className="w-full rounded-lg border border-[#F1F1F1] bg-white px-3 py-2.5 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-[#EB4C4C] focus:ring-2 focus:ring-[#EB4C4C]/20 disabled:cursor-not-allowed disabled:opacity-60"
              />
            </label>

            <label className="block space-y-2">
              <span className="text-sm font-semibold text-slate-700">Delimiter</span>
              <input
                type="text"
                value={delimiter}
                disabled={running}
                onChange={(ev) => setDelimiter(ev.target.value)}
                title="Use auto, tab, \\t, single-char (, ; |), or multi-char (||, ::)"
                aria-label="CSV delimiter or auto"
                placeholder="auto"
                className="w-full rounded-lg border border-[#F1F1F1] bg-white px-3 py-2.5 font-mono text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-[#EB4C4C] focus:ring-2 focus:ring-[#EB4C4C]/20 disabled:cursor-not-allowed disabled:opacity-60"
              />
              <span className="block text-xs text-slate-500">
                Recommended: <code>auto</code>. You can also use <code>tab</code>, <code>\t</code>, <code>|</code>, <code>||</code>, <code>::</code>.
              </span>
            </label>
          </div>

          <button
            type="submit"
            disabled={
              running ||
              !uidColumn.trim() ||
              (useLocalPaths
                ? !sourcePath.trim() || !targetPath.trim()
                : !sourceFile || !targetFile)
            }
            className="inline-flex w-full items-center justify-center gap-3 rounded-xl bg-[#EB4C4C] px-5 py-4 text-base font-semibold text-[#FFFDEF] shadow-[0_12px_30px_rgba(235,76,76,0.28)] transition duration-200 hover:-translate-y-0.5 hover:bg-[#d83e3e] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {running ? (
              <>
                <span
                  className="h-5 w-5 animate-spin rounded-full border-2 border-[#FFFDEF]/40 border-t-[#FFFDEF]"
                  aria-hidden
                />
                Running...
              </>
            ) : (
              'Run validation'
            )}
          </button>
        </form>
      </section>

      <div className="space-y-6" role="status" aria-live="polite">
        {running && jobUi ? (
          <section className="rounded-2xl border border-[#F1F1F1] border-l-4 border-l-[#EB4C4C] bg-white p-6 shadow-[0_12px_40px_rgba(235,76,76,0.10)]">
            <p
              className="mb-2 inline-block rounded-md border border-sky-300 bg-sky-100 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-sky-700"
              aria-hidden="true"
            >
              Async job - 202 Accepted
            </p>
            <p className="mb-1 text-lg font-bold text-[#EB4C4C]">{jobUi.title}</p>
            <p className="text-sm text-slate-600">{jobUi.body}</p>
            {jobProgress.message ? <p className="mt-2 text-sm text-slate-600">{jobProgress.message}</p> : null}
            {jobProgress.progress?.percent != null ? (
              <p className="mt-2 text-sm text-slate-600">
                Progress: <strong>{formatPercent(jobProgress.progress.percent)}</strong>
              </p>
            ) : null}
            {jobProgress.progress?.total_mismatch_records != null ? (
              <p className="mt-2 text-sm text-slate-600">
                Mismatches emitted so far: <strong>{Number(jobProgress.progress.total_mismatch_records)}</strong>
              </p>
            ) : null}
            {jobProgress.progress?.value_mismatch_done != null ? (
              <p className="mt-2 text-sm text-slate-600">
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
              <p className="mt-2 text-sm text-slate-600">
                Uploaded source: {formatBytes(Number(jobProgress.progress?.source_uploaded_bytes || 0))} | target:{' '}
                {formatBytes(Number(jobProgress.progress?.target_uploaded_bytes || 0))}
              </p>
            ) : null}
            {jobUi.extra ? <p className="mt-2 text-sm text-slate-600">{jobUi.extra}</p> : null}
            <p className="mt-3 text-sm font-medium text-slate-700">
              <strong>{(elapsedMs / 1000).toFixed(1)}s</strong> elapsed
            </p>
          </section>
        ) : null}

        {phase === 'success' && result ? (
          <section className="rounded-2xl border border-emerald-300 border-l-4 border-l-emerald-500 bg-emerald-50 p-6">
            <p className="mb-4 text-lg font-bold text-emerald-900">Finished</p>

            <p className="mb-2 pt-4 text-sm font-semibold uppercase tracking-wider text-slate-700">Summary of the search</p>

            <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl bg-white p-4 shadow-sm">
                <span className="block text-xs font-semibold uppercase tracking-widest text-slate-500">Fully Match</span>
                <span className="mt-1 block font-mono text-2xl font-black text-slate-900">
                  {result.summary?.is_match ? 'Yes' : 'No'}
                </span>
              </div>
              <div className="rounded-xl bg-white p-4 shadow-sm">
                <span className="block text-xs font-semibold uppercase tracking-widest text-slate-500">Source rows</span>
                <span className="mt-1 block font-mono text-2xl font-black text-slate-900">
                  {result.summary?.source_row_count ?? '-'}
                </span>
              </div>
              <div className="rounded-xl bg-white p-4 shadow-sm">
                <span className="block text-xs font-semibold uppercase tracking-widest text-slate-500">Target rows</span>
                <span className="mt-1 block font-mono text-2xl font-black text-slate-900">
                  {result.summary?.target_row_count ?? '-'}
                </span>
              </div>
              <div className="rounded-xl bg-white p-4 shadow-sm">
                <span className="block text-xs font-semibold uppercase tracking-widest text-slate-500">Mismatch records</span>
                <span className="mt-1 block font-mono text-2xl font-black text-slate-900">
                  {result.summary?.total_mismatch_records ?? '-'}
                </span>
              </div>
            </div>

            <p className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-700">Mismatch counts</p>
            <ul className="text-sm text-slate-700 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <li>
                <div className="rounded-xl bg-white p-4 shadow-sm">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-slate-500">Missing in Target</span>
                  <span className="mt-1 block font-mono text-2xl font-black text-slate-900">
                    {result.mismatch_counts?.missing_in_target ?? 0}
                  </span>
                </div>
              </li>
              <li>
                <div className="rounded-xl bg-white p-4 shadow-sm">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-slate-500">Extra in Target</span>
                  <span className="mt-1 block font-mono text-2xl font-black text-slate-900">
                    {result.mismatch_counts?.extra_in_target ?? 0}
                  </span>
                </div>
              </li>
              <li>
                <div className="rounded-xl bg-white p-4 shadow-sm">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-slate-500">Value Mismatched</span>
                  <span className="mt-1 block font-mono text-2xl font-black text-slate-900">
                    {result.mismatch_counts?.value_mismatch ?? 0}
                  </span>
                </div>
              </li>
            </ul>

            {result.run_id ? (
              <p className="mt-4 text-sm text-slate-700">
                Run id: <code>{result.run_id}</code>
              </p>
            ) : null}

            {result.mismatch_samples?.length ? (
              <>
                {/* <p className="mt-6 mb-2 text-sm font-semibold uppercase tracking-wider text-slate-700">Sample mismatches</p>
                <div className="overflow-x-auto rounded-xl border border-[#F1F1F1] bg-white">
                  <table className="min-w-full border-collapse text-left text-sm">
                    <thead>
                      <tr className="bg-[#FFFDEF] text-xs uppercase tracking-wide text-slate-600">
                        <th className="px-3 py-2 font-semibold">UID</th>
                        <th className="px-3 py-2 font-semibold">Type</th>
                        <th className="px-3 py-2 font-semibold">Column</th>
                        <th className="px-3 py-2 font-semibold">Expected (source)</th>
                        <th className="px-3 py-2 font-semibold">Actual (target)</th>
                      </tr>
                    </thead>
                    <MismatchSampleRows samples={result.mismatch_samples} />
                  </table>
                </div> */}
                <button
                  type="button"
                  onClick={() => navigate('/report', { state: { result } })}
                  className="inline-flex w-full items-center justify-center gap-3 rounded-xl bg-emerald-400 px-5 py-4 text-base font-semibold text-[#FFFDEF] shadow-[0_12px_30px_rgba(235,76,76,0.28)] transition duration-200 hover:-translate-y-0.5 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60 mb-4 mt-10"
                >

                  View Detailed Report

                </button>
              </>
            ) : null}
          </section>
        ) : null}

        {phase === 'error' ? (
          <section className="rounded-2xl border border-rose-300 border-l-4 border-l-rose-500 bg-rose-50 p-6">
            <p className="mb-2 text-lg font-bold text-rose-900">Something went wrong</p>
            <p className="whitespace-pre-wrap break-words text-sm text-rose-800">{errorMessage}</p>
          </section>
        ) : null}
      </div>
    </div>
  )
}