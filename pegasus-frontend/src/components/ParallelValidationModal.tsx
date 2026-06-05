import { useCallback, useEffect, useState } from 'react'
import { Button, Modal, Space, Typography } from 'antd'
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

export default function ParallelValidationModal({ open, onClose, onConfirm }: any) {
  const [queueInfo, setQueueInfo] = useState<any>(null)
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

  return (
    <Modal
      open
      onCancel={onClose}
      centered
      width={960}
      footer={null}
      title={<Typography.Title level={3} style={{ margin: 0 }}>Review resources before running</Typography.Title>}
      styles={{ body: { maxHeight: '90vh', overflow: 'auto' } }}
    >
      <Space direction="vertical" size={20} style={{ width: '100%' }}>
        <Typography.Text type="secondary">Set max parallel jobs and auto-tune before starting validation.</Typography.Text>

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

        {applyError ? <Typography.Text type="danger">{applyError}</Typography.Text> : null}

        <Space>
          <Button type="primary" size="large" loading={loading} disabled={queueLoading} onClick={handleConfirm}>
            Run validation
          </Button>
          <Button disabled={loading} onClick={onClose}>
            Cancel
          </Button>
        </Space>
      </Space>
    </Modal>
  )
}