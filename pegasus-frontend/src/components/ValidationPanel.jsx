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

  // ── Queue / concurrency state ──
  const [queueInfo, setQueueInfo] = useState(null)
  const [concurrencySlider, setConcurrencySlider] = useState(2)
  const [concurrencyUpdating, setConcurrencyUpdating] = useState(false)
  const [concurrencyError, setConcurrencyError] = useState('')
  const [showQueueSettings, setShowQueueSettings] = useState(false)

  const running = phase === 'running'

  // Fetch queue info on mount
  useEffect(() => {
    async function fetchQueue() {
      try {
        const res = await fetch(absoluteApiUrl('/api/v1/validate/queue'))
        if (res.ok) {
          const data = await res.json()
          setQueueInfo(data)
          setConcurrencySlider(data.max_concurrency ?? 2)
        }
      } catch { /* silent */ }
    }
    fetchQueue()
  }, [])

  async function handleConcurrencyUpdate(newValue, autoTuneEnabled) {
    setConcurrencyUpdating(true)
    setConcurrencyError('')
    try {
      const body = {}
      if (newValue != null) body.max_concurrency = newValue
      if (autoTuneEnabled != null) body.auto_tune_enabled = autoTuneEnabled
      const res = await fetch(absoluteApiUrl('/api/v1/validate/queue'), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.ok) {
        const data = await res.json()
        setQueueInfo(data)
        setConcurrencySlider(data.max_concurrency)
      } else {
        const err = await res.json().catch(() => ({}))
        setConcurrencyError(err.detail || `Failed (${res.status})`)
      }
    } catch (e) {
      setConcurrencyError(e.message)
    } finally {
      setConcurrencyUpdating(false)
    }
  }

  // Timer for elapsed time
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
      // Refresh queue info after completion
      try {
        const qres = await fetch(absoluteApiUrl('/api/v1/validate/queue'))
        if (qres.ok) setQueueInfo(await qres.json())
      } catch { /* silent */ }
    } catch (err) {
      setPhase('error')
      setErrorMessage(err instanceof Error ? err.message : String(err))
    }
  }

  const cpuCores = queueInfo?.cpu_cores_available ?? null
  const ra = queueInfo?.resource_advisor ?? null

  return (
    <div className="space-y-8">
      {/* ── Concurrency Settings Panel ── */}
      <section className="rounded-2xl border border-[#F1F1F1] bg-white p-5 shadow-[0_8px_30px_rgba(0,0,0,0.06)] sm:p-6">
        <button
          type="button"
          onClick={() => setShowQueueSettings((v) => !v)}
          className="flex w-full items-center justify-between text-left"
        >
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#EB4C4C] to-[#FF7676] text-sm font-bold text-white shadow-sm">⚡</span>
            <div>
              <p className="text-sm font-semibold text-slate-800">Parallel Validation</p>
              <p className="text-xs text-slate-500">
                {cpuCores
                  ? `${queueInfo?.max_concurrency ?? '?'} of ${cpuCores} cores allocated`
                  : 'Loading server info…'}
                {queueInfo ? ` · ${queueInfo.running} running · ${queueInfo.pending} queued` : ''}
                {ra?.recommended_max_concurrency != null
                  ? ` · recommended: ${ra.recommended_max_concurrency}`
                  : ''}
              </p>
            </div>
          </div>
          <span className={`text-slate-400 transition-transform duration-200 ${showQueueSettings ? 'rotate-180' : ''}`}>
            ▾
          </span>
        </button>

        {showQueueSettings && cpuCores ? (
          <div className="mt-4 space-y-5 border-t border-[#F1F1F1] pt-4">

            {/* Resource status bar */}
            {ra ? (
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-[#F1F1F1] bg-[#FAFAFA] p-3">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-slate-400">RAM</span>
                  <span className="mt-1 block font-mono text-lg font-bold text-slate-800">
                    {ra.system?.available_ram_gib ?? '?'} <span className="text-sm font-normal text-slate-500">/ {ra.system?.total_ram_gib ?? '?'} GiB free</span>
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-400">
                    ~{ra.per_job_estimate?.ram_mib ?? '?'} MiB per job
                  </span>
                </div>
                <div className="rounded-lg border border-[#F1F1F1] bg-[#FAFAFA] p-3">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-slate-400">Disk</span>
                  <span className="mt-1 block font-mono text-lg font-bold text-slate-800">
                    {ra.system?.available_disk_gib ?? '?'} <span className="text-sm font-normal text-slate-500">/ {ra.system?.total_disk_gib ?? '?'} GiB free</span>
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-400">
                    ~{ra.per_job_estimate?.disk_mib ?? '?'} MiB per job
                  </span>
                </div>
                <div className="rounded-lg border border-[#F1F1F1] bg-[#FAFAFA] p-3">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-slate-400">Safe limits</span>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs">
                    <span className="rounded bg-blue-100 px-1.5 py-0.5 font-semibold text-blue-700">RAM: {ra.limits?.max_safe_by_ram ?? '?'}</span>
                    <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-semibold text-emerald-700">Disk: {ra.limits?.max_safe_by_disk ?? '?'}</span>
                    <span className="rounded bg-purple-100 px-1.5 py-0.5 font-semibold text-purple-700">CPU: {ra.limits?.max_safe_by_cpu ?? '?'}</span>
                  </div>
                  <span className="mt-1 block text-xs font-semibold text-[#EB4C4C]">
                    Recommended: {ra.recommended_max_concurrency ?? '?'}
                  </span>
                </div>
              </div>
            ) : null}

            {/* Warnings */}
            {ra?.warnings?.length ? (
              <div className="space-y-2">
                {ra.warnings.map((w, i) => (
                  <div key={i} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    ⚠️ {w}
                  </div>
                ))}
              </div>
            ) : null}

            {/* Slider */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-semibold text-slate-700" htmlFor="concurrency-slider">
                  Max parallel jobs
                </label>
                <div className="flex items-center gap-2">
                  {ra?.recommended_max_concurrency != null && concurrencySlider !== ra.recommended_max_concurrency ? (
                    <button
                      type="button"
                      onClick={() => setConcurrencySlider(ra.recommended_max_concurrency)}
                      className="rounded bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700 hover:bg-blue-200 transition"
                    >
                      Use recommended ({ra.recommended_max_concurrency})
                    </button>
                  ) : null}
                  <span className="rounded-md bg-[#FFFDEF] px-2.5 py-1 font-mono text-sm font-bold text-[#EB4C4C]">
                    {concurrencySlider}
                  </span>
                </div>
              </div>

              <input
                id="concurrency-slider"
                type="range"
                min={1}
                max={Math.min(cpuCores, 32)}
                step={1}
                value={concurrencySlider}
                disabled={concurrencyUpdating}
                onChange={(ev) => setConcurrencySlider(Number(ev.target.value))}
                className="w-full cursor-pointer accent-[#EB4C4C] disabled:cursor-not-allowed disabled:opacity-50"
              />

              <div className="mt-1 flex justify-between text-xs text-slate-400">
                <span>1 (serial)</span>
                <span>{cpuCores} cores</span>
              </div>
            </div>

            {/* Auto-tune toggle */}
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={queueInfo?.auto_tune_enabled ?? true}
                disabled={concurrencyUpdating}
                onChange={(ev) => {
                  const enabled = ev.target.checked
                  handleConcurrencyUpdate(concurrencySlider, enabled)
                }}
                className="h-4 w-4 rounded border-slate-300 text-[#EB4C4C] accent-[#EB4C4C] focus:ring-[#EB4C4C]"
              />
              <div>
                <span className="text-sm font-semibold text-slate-700">Auto-tune</span>
                <span className="ml-2 text-xs text-slate-500">
                  Dynamically cap concurrency based on available RAM, disk &amp; swap pressure
                </span>
              </div>
            </label>

            {/* Apply button */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                disabled={concurrencyUpdating || concurrencySlider === queueInfo?.max_concurrency}
                onClick={() => handleConcurrencyUpdate(concurrencySlider)}
                className="rounded-lg bg-[#EB4C4C] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#d83e3e] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {concurrencyUpdating ? 'Applying…' : 'Apply'}
              </button>
              {concurrencySlider === queueInfo?.max_concurrency ? (
                <span className="text-xs text-emerald-600 font-medium">✓ Current setting</span>
              ) : null}
              {concurrencyError ? (
                <span className="text-xs text-rose-600">{concurrencyError}</span>
              ) : null}
            </div>

            <p className="text-xs text-slate-500 leading-relaxed">
              Your server has <strong>{cpuCores} CPU cores</strong>,{' '}
              <strong>{ra?.system?.total_ram_gib ?? '?'} GiB RAM</strong>, and{' '}
              <strong>{ra?.system?.available_disk_gib ?? '?'} GiB disk free</strong>.
              The system recommends <strong>{ra?.recommended_max_concurrency ?? '?'}</strong> parallel jobs
              based on current resource availability.
              {queueInfo?.auto_tune_enabled
                ? ' Auto-tune is ON — effective concurrency may be lower than your setting if resources are tight.'
                : ' Auto-tune is OFF — only your manual setting is used.'}
            </p>
          </div>
        ) : null}
      </section>
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
            {jobProgress.phase === 'queued' && jobProgress.progress?.queue_position != null ? (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
                <p className="text-sm font-semibold text-amber-800">
                  Queue position: {Number(jobProgress.progress.queue_position) + 1}
                  {jobProgress.progress?.max_concurrency ? (
                    <span className="font-normal text-amber-600">
                      {' '}· {jobProgress.progress.running_jobs ?? '?'}/{jobProgress.progress.max_concurrency} workers active
                    </span>
                  ) : null}
                </p>
                <p className="mt-1 text-xs text-amber-600">
                  Your job will start when a running validation finishes.
                </p>
              </div>
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