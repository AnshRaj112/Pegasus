import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

function absoluteApiUrl(pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl
  const base = apiBase.replace(/\/$/, '')
  const path = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`
  return base ? `${base}${path}` : path
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

export default function ParallelValidationModal({ open, onClose, onConfirm }) {
  const [queueInfo, setQueueInfo] = useState(null)
  const [concurrencySlider, setConcurrencySlider] = useState(2)
  const [autoTuneEnabled, setAutoTuneEnabled] = useState(true)
  const [loading, setLoading] = useState(false)
  const [queueLoading, setQueueLoading] = useState(false)
  const [queueError, setQueueError] = useState('')
  const [applyError, setApplyError] = useState('')

  const refreshQueue = useCallback(async () => {
    setQueueLoading(true)
    setQueueError('')
    try {
      const res = await fetch(absoluteApiUrl('/api/v1/validate/queue'))
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(formatDetail(err.detail) || `Queue status failed (${res.status})`)
      }
      const data = await res.json()
      setQueueInfo(data)
      setConcurrencySlider(data.max_concurrency ?? 2)
      setAutoTuneEnabled(data.auto_tune_enabled ?? true)
    } catch (e) {
      setQueueError(e instanceof Error ? e.message : String(e))
    } finally {
      setQueueLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    setApplyError('')
    refreshQueue()
  }, [open, refreshQueue])

  const ra = queueInfo?.resource_advisor ?? null
  const cpuCores = queueInfo?.cpu_cores_available ?? null
  const effectiveMax = queueInfo?.effective_max_concurrency ?? null
  const sliderMax = Math.max(
    1,
    concurrencySlider,
    cpuCores ?? 1,
    ra?.recommended_max_concurrency ?? 1,
    ra?.limits?.max_safe_by_ram ?? 1,
    ra?.limits?.max_safe_by_disk ?? 1,
    queueInfo?.max_concurrency ?? 1,
  )

  async function handleConfirm() {
    setLoading(true)
    setApplyError('')
    try {
      const res = await fetch(absoluteApiUrl('/api/v1/validate/queue'), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_concurrency: concurrencySlider,
          auto_tune_enabled: autoTuneEnabled,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(formatDetail(err.detail) || `Failed to apply settings (${res.status})`)
      }
      setQueueInfo(await res.json())
      const ok = await onConfirm()
      if (ok !== false) onClose()
    } catch (e) {
      setApplyError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  if (!open) return null

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="parallel-validation-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <button
        type="button"
        aria-label="Close backdrop"
        onClick={onClose}
        disabled={loading}
        style={{
          position: 'absolute',
          inset: 0,
          border: 'none',
          background: 'rgba(0, 0, 0, 0.72)',
          cursor: loading ? 'not-allowed' : 'pointer',
        }}
      />
      <div
        style={{
          position: 'relative',
          width: 'min(920px, 100%)',
          maxHeight: 'min(90vh, 900px)',
          overflow: 'auto',
          borderRadius: 16,
          border: '1px solid var(--border-2)',
          background: 'var(--surface-1)',
          boxShadow: '0 24px 80px rgba(0, 0, 0, 0.55)',
          padding: '28px 28px 24px',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          disabled={loading}
          aria-label="Close dialog"
          style={{
            position: 'absolute',
            top: 16,
            right: 16,
            width: 32,
            height: 32,
            border: 'none',
            borderRadius: 8,
            background: 'var(--surface-3)',
            color: 'var(--text-2)',
            fontSize: 20,
            lineHeight: 1,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          ×
        </button>

        <p style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 6 }}>
          Parallel validation
        </p>
        <h2 id="parallel-validation-title" style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', marginBottom: 8 }}>
          Review resources before running
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)', marginBottom: 20, maxWidth: 640 }}>
          Set how many validation jobs may run in parallel. Auto-tune lowers the effective cap when RAM, disk, or swap are tight.
        </p>

        {queueLoading ? <p style={{ fontSize: 13, color: 'var(--text-3)', marginBottom: 16 }}>Loading server resources…</p> : null}
        {queueError ? (
          <div style={{ marginBottom: 16, padding: '10px 12px', borderRadius: 8, background: 'var(--danger-muted)', border: '1px solid var(--danger-border)', fontSize: 12, color: 'var(--danger)' }}>
            {queueError}
            <button type="button" onClick={refreshQueue} className="btn btn-ghost" style={{ marginLeft: 8, padding: '2px 8px', fontSize: 11 }}>
              Retry
            </button>
          </div>
        ) : null}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginBottom: 16 }}>
          <ResourceCard label="RAM" value={`${ra?.system?.available_ram_gib ?? '?'} / ${ra?.system?.total_ram_gib ?? '?'} GiB`} hint={`~${ra?.per_job_estimate?.ram_mib ?? '?'} MiB per job`} />
          <ResourceCard label="Disk" value={`${ra?.system?.available_disk_gib ?? '?'} / ${ra?.system?.total_disk_gib ?? '?'} GiB`} hint={`~${ra?.per_job_estimate?.disk_mib ?? '?'} MiB per job`} />
          <ResourceCard
            label="Safe limits"
            value={`Recommended: ${ra?.recommended_max_concurrency ?? '?'}`}
            hint={`RAM ${ra?.limits?.max_safe_by_ram ?? '?'} · Disk ${ra?.limits?.max_safe_by_disk ?? '?'} · CPU ${ra?.limits?.max_safe_by_cpu ?? '?'}`}
          />
        </div>

        {ra?.warnings?.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
            {ra.warnings.map((w, i) => (
              <div key={i} style={{ padding: '8px 12px', borderRadius: 8, background: 'rgba(249, 115, 22, 0.1)', border: '1px solid var(--accent-border)', fontSize: 12, color: 'var(--accent-hover)' }}>
                {w}
              </div>
            ))}
          </div>
        ) : null}

        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
            <label htmlFor="pegasus-concurrency-range" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>
              Max parallel jobs
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {ra?.recommended_max_concurrency != null && concurrencySlider !== ra.recommended_max_concurrency ? (
                <button type="button" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 11 }} onClick={() => setConcurrencySlider(ra.recommended_max_concurrency)}>
                  Use recommended ({ra.recommended_max_concurrency})
                </button>
              ) : null}
              <input
                type="number"
                min={1}
                value={concurrencySlider}
                disabled={loading || queueLoading}
                onChange={(ev) => {
                  const n = Number(ev.target.value)
                  if (Number.isFinite(n) && n >= 1) setConcurrencySlider(Math.floor(n))
                }}
                className="input input-mono"
                style={{ width: 72, textAlign: 'center' }}
                aria-label="Max parallel jobs"
              />
            </div>
          </div>
          <input
            id="pegasus-concurrency-range"
            type="range"
            min={1}
            max={sliderMax}
            step={1}
            value={Math.min(concurrencySlider, sliderMax)}
            disabled={loading || queueLoading}
            onChange={(ev) => setConcurrencySlider(Number(ev.target.value))}
            style={{ width: '100%', accentColor: 'var(--accent)' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>
            <span>1 (serial)</span>
            <span>up to {sliderMax}</span>
          </div>
          {effectiveMax != null && autoTuneEnabled && effectiveMax < concurrencySlider ? (
            <p style={{ marginTop: 8, fontSize: 12, color: 'var(--accent-hover)' }}>
              Effective cap now: <strong>{effectiveMax}</strong> (auto-tune; your setting is {concurrencySlider})
            </p>
          ) : null}
        </div>

        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 20, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={autoTuneEnabled}
            disabled={loading || queueLoading}
            onChange={(ev) => setAutoTuneEnabled(ev.target.checked)}
            style={{ marginTop: 2, accentColor: 'var(--accent)' }}
          />
          <span>
            <span style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>Auto-tune</span>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>Cap concurrency from live RAM, disk, and swap</span>
          </span>
        </label>

        {applyError ? <p style={{ fontSize: 12, color: 'var(--danger)', marginBottom: 12 }}>{applyError}</p> : null}

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button type="button" className="btn btn-primary btn-lg" disabled={loading || queueLoading} onClick={handleConfirm}>
            {loading ? 'Starting…' : 'Run validation'}
          </button>
          <button type="button" className="btn btn-secondary" disabled={loading} onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function ResourceCard({ label, value, hint }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: 10, background: 'var(--surface-2)', border: '1px solid var(--border-1)' }}>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace' }}>{value}</div>
      {hint ? <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>{hint}</div> : null}
    </div>
  )
}
