import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import ParallelValidationResourceForm from './ParallelValidationResourceForm'

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
          width: 'min(960px, 100%)',
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
        <p style={{ fontSize: 13, color: 'var(--text-3)', marginBottom: 20, maxWidth: 720 }}>
          Set max parallel jobs and auto-tune before starting validation.
        </p>

        <ParallelValidationResourceForm
          queueInfo={queueInfo}
          queueLoading={queueLoading}
          queueError={queueError}
          concurrencySlider={concurrencySlider}
          onConcurrencyChange={setConcurrencySlider}
          autoTuneEnabled={autoTuneEnabled}
          onAutoTuneChange={setAutoTuneEnabled}
          onRefresh={refreshQueue}
          disabled={loading || queueLoading}
          theme="light"
        />

        {applyError ? <p style={{ fontSize: 12, color: 'var(--danger)', marginTop: 16 }}>{applyError}</p> : null}

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border-1)' }}>
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