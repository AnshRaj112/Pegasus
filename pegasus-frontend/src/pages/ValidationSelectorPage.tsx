import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Form, Select, Input, Button, Modal, Row, Col, Space, Progress, Badge, Alert, Typography } from 'antd'
import { PlayCircleOutlined, SettingOutlined, CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import LocalPathBrowser from '../components/LocalPathBrowser'
import ParallelValidationResourceForm from '../components/ParallelValidationResourceForm'
import { formatJobError } from '../api/formatError'
import { absoluteApiUrl } from '../api/http'
import { pollValidationJob, normalizeValidateResult } from '../api/validationPoll'

const { Title, Paragraph, Text } = Typography

const pollTimeoutRaw = Number((import.meta as any).env.VITE_VALIDATION_POLL_TIMEOUT_MS ?? 0)
const pollTimeoutMs = Number.isFinite(pollTimeoutRaw) ? pollTimeoutRaw : 0

function formatPercent(n: number) {
  if (!Number.isFinite(n)) return null
  return `${Math.max(0, Math.min(100, Number(n))).toFixed(1)}%`
}

export default function ValidationSelectorPage() {
  const navigate = useNavigate()
  const [form] = Form.useForm()

  const [sourcePath, setSourcePath] = useState('')
  const [targetPath, setTargetPath] = useState('')
  const [fileFormat, setFileFormat] = useState('csv')
  const [uidColumn, setUidColumn] = useState('id')
  const [delimiter, setDelimiter] = useState('auto')

  const [phase, setPhase] = useState<'idle' | 'running' | 'success' | 'error'>('idle')
  const [elapsedMs, setElapsedMs] = useState(0)
  const [result, setResult] = useState<any>(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [showParallelValidationModal, setShowParallelValidationModal] = useState(false)
  const [jobProgress, setJobProgress] = useState({ phase: 'queued', jobId: null as string | null, message: '', progress: {} as any })
  const [queueInfo, setQueueInfo] = useState<any>(null)
  const [concurrencySlider, setConcurrencySlider] = useState(2)
  const [autoTuneLocal, setAutoTuneLocal] = useState(true)
  const [concurrencyUpdating, setConcurrencyUpdating] = useState(false)
  const [concurrencyError, setConcurrencyError] = useState('')
  const [queueModalLoading, setQueueModalLoading] = useState(false)
  const [queueModalError, setQueueModalError] = useState('')

  const running = phase === 'running'
  const effectiveMax = queueInfo?.effective_max_concurrency ?? null

  async function refreshQueueInfo() {
    setQueueModalLoading(true)
    setQueueModalError('')
    try {
      const res = await fetch(absoluteApiUrl('/api/v1/validate/queue')!)
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail ? JSON.stringify(err.detail) : `Queue status failed (${res.status})`)
      }
      const data = await res.json()
      setQueueInfo(data)
      setConcurrencySlider(data.max_concurrency ?? 2)
      setAutoTuneLocal(data.auto_tune_enabled ?? true)
    } catch (e: any) {
      setQueueModalError(e.message || String(e))
    } finally {
      setQueueModalLoading(false)
    }
  }

  useEffect(() => {
    refreshQueueInfo()
  }, [])

  useEffect(() => {
    if (!showParallelValidationModal) return
    refreshQueueInfo()
  }, [showParallelValidationModal])

  useEffect(() => {
    if (!running) return
    const start = performance.now()
    const id = setInterval(() => setElapsedMs(Math.round(performance.now() - start)), 100)
    return () => clearInterval(id)
  }, [running])

  function handleOpenParallelValidation(e: React.FormEvent) {
    e.preventDefault()
    if (!sourcePath.trim() || !targetPath.trim()) return
    setShowParallelValidationModal(true)
  }

  async function executeValidation() {
    setConcurrencyUpdating(true)
    setConcurrencyError('')
    try {
      const res = await fetch(absoluteApiUrl('/api/v1/validate/queue')!, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_concurrency: concurrencySlider,
          auto_tune_enabled: autoTuneLocal,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        setConcurrencyError(err.detail ? JSON.stringify(err.detail) : `Failed to apply settings (${res.status})`)
        return
      }
      setQueueInfo(await res.json())
    } catch (e: any) {
      setConcurrencyError(e.message || String(e))
      return
    } finally {
      setConcurrencyUpdating(false)
    }

    setShowParallelValidationModal(false)
    setPhase('running')
    setElapsedMs(0)
    setResult(null)
    setErrorMessage('')
    setJobProgress({ phase: 'queued', jobId: null, message: '', progress: {} })

    try {
      const res = await fetch(absoluteApiUrl('/api/v1/validate/local')!, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          fileFormat === 'json'
            ? {
                source_path: sourcePath.trim(),
                target_path: targetPath.trim(),
                file_format: 'json',
                delimiter: 'json',
                uid_column: 'document',
              }
            : {
                source_path: sourcePath.trim(),
                target_path: targetPath.trim(),
                uid_column: uidColumn.trim(),
                delimiter: delimiter.trim() || 'auto',
                file_format: 'csv',
              }
        ),
      })

      const raw = await res.text()
      let data: any = {}
      if (raw) {
        try {
          data = JSON.parse(raw)
        } catch {
          data = { detail: raw.trim().slice(0, 800) || `Non-JSON response (${res.status})` }
        }
      }

      if (!res.ok) {
        const msg = data.detail ? JSON.stringify(data.detail) : raw?.trim()?.slice(0, 800) || ''
        throw new Error(msg || `${res.status} ${res.statusText}`)
      }

      let final = data
      if (res.status === 202 && data.poll_url) {
        const jid = data.job_id != null ? String(data.job_id) : null
        setJobProgress({ phase: 'accepted', jobId: jid, message: '', progress: {} })
        final = await pollValidationJob(data.poll_url, {
          timeoutMs: pollTimeoutMs,
          onPoll: (payload: any) => {
            const st = payload?.status
            const phaseName = payload?.phase || (st === 'running' ? 'running' : st) || 'running'
            setJobProgress((prev) => ({
              ...prev,
              phase: phaseName,
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
      try {
        const qres = await fetch(absoluteApiUrl('/api/v1/validate/queue')!)
        if (qres.ok) setQueueInfo(await qres.json())
      } catch {
        // silent
      }
    } catch (err: any) {
      setPhase('error')
      setErrorMessage(formatJobError(err.message || String(err)))
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <Title level={3} style={{ margin: 0 }}>File Validation Selector</Title>
        <Paragraph type="secondary">
          Configure format settings, select target server paths, and dispatch validation comparisons.
        </Paragraph>
      </div>

      <Row gutter={24}>
        {/* Left Options Form Column */}
        <Col span={16}>
          <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <form onSubmit={handleOpenParallelValidation} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <Row gutter={16}>
                <Col span={12}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <Text strong style={{ fontSize: '13px' }}>File Format</Text>
                    <Select
                      value={fileFormat}
                      disabled={running}
                      onChange={(val) => setFileFormat(val)}
                      options={[
                        { value: 'csv', label: 'CSV / Delimited File' },
                        { value: 'json', label: 'JSON Document' }
                      ]}
                    />
                  </div>
                </Col>
              </Row>

              <LocalPathBrowser
                label={fileFormat === 'json' ? 'Source JSON (Expected)' : 'Source CSV (Expected)'}
                value={sourcePath}
                onChange={setSourcePath}
                disabled={running}
              />

              <LocalPathBrowser
                label={fileFormat === 'json' ? 'Target JSON (Actual)' : 'Target CSV (Actual)'}
                value={targetPath}
                onChange={setTargetPath}
                disabled={running}
              />

              {fileFormat === 'json' ? (
                <Alert message="JSON comparisons are conducted on whole documents with keys and array orders re-sorted (order-agnostic matching)." type="info" showIcon />
              ) : (
                <Row gutter={16}>
                  <Col span={12}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <Text strong style={{ fontSize: '13px' }}>UID Column</Text>
                      <Input
                        value={uidColumn}
                        disabled={running}
                        onChange={(e) => setUidColumn(e.target.value)}
                        placeholder="e.g. id"
                      />
                    </div>
                  </Col>
                  <Col span={12}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <Text strong style={{ fontSize: '13px' }}>CSV Delimiter</Text>
                      <Input
                        value={delimiter}
                        disabled={running}
                        onChange={(e) => setDelimiter(e.target.value)}
                        placeholder="auto"
                      />
                      <Text type="secondary" style={{ fontSize: '11px' }}>
                        Supports <code>auto</code>, <code>tab</code>, <code>|</code>, etc.
                      </Text>
                    </div>
                  </Col>
                </Row>
              )}

              <Button
                type="primary"
                htmlType="submit"
                disabled={running || !sourcePath.trim() || !targetPath.trim() || (fileFormat !== 'json' && !uidColumn.trim())}
                icon={<PlayCircleOutlined />}
                size="large"
                style={{ height: '48px', fontWeight: 600 }}
                block
              >
                {running ? 'Running Validation...' : 'Run Validation'}
              </Button>
            </form>
          </Card>
        </Col>

        {/* Right Status Panel Column */}
        <Col span={8}>
          {running && (
            <Card title="Background Worker Running" bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: '16px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <Badge status="processing" text={jobProgress.phase.toUpperCase()} style={{ fontWeight: 600 }} />
                {jobProgress.message && (
                  <Text type="secondary">{jobProgress.message}</Text>
                )}
                {jobProgress.progress?.percent != null && (
                  <div>
                    <Text strong>Progress: </Text>
                    <Progress percent={Math.round(jobProgress.progress.percent)} status="active" />
                  </div>
                )}
                {jobProgress.progress?.total_mismatch_records != null && (
                  <div>
                    <Text type="secondary">Mismatches found: </Text>
                    <Text strong>{jobProgress.progress.total_mismatch_records}</Text>
                  </div>
                )}
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  Elapsed time: {Math.round(elapsedMs / 1000)}s
                </Text>
              </div>
            </Card>
          )}

          {phase === 'success' && result && (
            <Card
              title={
                <Space>
                  <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  <Text strong>Validation Completed</Text>
                </Space>
              }
              bordered={false}
              style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)', borderTop: '4px solid #52c41a' }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div>
                  <Text type="secondary">Result: </Text>
                  <Tag color={result.summary?.is_match ? 'success' : 'error'}>
                    {result.summary?.is_match ? 'FULL MATCH' : 'MISMATCH DETECTED'}
                  </Tag>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <div>
                    <Text type="secondary" style={{ fontSize: '11px' }}>Source Rows</Text>
                    <div>{result.summary?.source_row_count ?? '—'}</div>
                  </div>
                  <div>
                    <Text type="secondary" style={{ fontSize: '11px' }}>Target Rows</Text>
                    <div>{result.summary?.target_row_count ?? '—'}</div>
                  </div>
                </div>

                <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: '10px' }}>
                  <Text strong style={{ fontSize: '12px', display: 'block', marginBottom: '6px' }}>Mismatch Details</Text>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text type="secondary">Missing in Target</Text>
                      <Text strong>{result.mismatch_counts?.missing_in_target ?? 0}</Text>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text type="secondary">Extra in Target</Text>
                      <Text strong>{result.mismatch_counts?.extra_in_target ?? 0}</Text>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text type="secondary">Value Mismatches</Text>
                      <Text strong>{result.mismatch_counts?.value_mismatch ?? 0}</Text>
                    </div>
                  </div>
                </div>

                <Button
                  type="primary"
                  onClick={() => navigate('/report', { state: { result } })}
                  icon={<SettingOutlined />}
                  block
                >
                  View Detailed Report
                </Button>
              </div>
            </Card>
          )}

          {phase === 'error' && (
            <Alert
              message="Job Execution Failed"
              description={errorMessage}
              type="error"
              showIcon
              style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}
            />
          )}
        </Col>
      </Row>

      {/* Parallel Validation Settings Modal */}
      <Modal
        title={
          <div>
            <div style={{ fontSize: '12px', color: '#1890ff', textTransform: 'uppercase', fontWeight: 600 }}>Parallel Validation</div>
            <Title level={4} style={{ margin: '4px 0 0 0' }}>Review Resources & Run</Title>
          </div>
        }
        open={showParallelValidationModal}
        onCancel={() => setShowParallelValidationModal(false)}
        footer={[
          <Button key="cancel" disabled={concurrencyUpdating} onClick={() => setShowParallelValidationModal(false)}>
            Cancel
          </Button>,
          <Button key="run" type="primary" loading={concurrencyUpdating} disabled={queueModalLoading} onClick={executeValidation}>
            Run Validation
          </Button>
        ]}
        centered
        width={720}
        destroyOnClose
      >
        <div style={{ padding: '12px 0' }}>
          <ParallelValidationResourceForm
            queueInfo={queueInfo}
            queueLoading={queueModalLoading}
            queueError={queueModalError}
            concurrencySlider={concurrencySlider}
            onConcurrencyChange={setConcurrencySlider}
            autoTuneEnabled={autoTuneLocal}
            onAutoTuneChange={setAutoTuneLocal}
            onRefresh={refreshQueueInfo}
            disabled={concurrencyUpdating}
            theme="light"
          />
          {concurrencyError && (
            <Alert message={concurrencyError} type="error" showIcon style={{ marginTop: '12px' }} />
          )}
        </div>
      </Modal>
    </div>
  )
}
