import { useEffect, useState } from 'react'
import { Alert, Button, Card, Col, Input, Row, Select, Space, Statistic, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import LocalPathBrowser from './LocalPathBrowser'
import ValidationJobProgress from './ValidationJobProgress'
import { formatJobError } from '../api/formatError.js'
import { formatDuration } from '../api/validationHistory.js'

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

function flattenMismatchSampleGroups(groups) {
  if (!groups) return []
  return [
    ...(groups.missing_in_target ?? []),
    ...(groups.extra_in_target ?? []),
    ...(groups.value_mismatch ?? []),
  ]
}

function normalizeValidateResult(data) {
  if (!data) return data
  if ((data.mismatch_samples?.length ?? 0) > 0) return data
  const flattened = flattenMismatchSampleGroups(data.mismatch_sample_groups)
  if (flattened.length === 0) return data
  return { ...data, mismatch_samples: flattened }
}

async function pollValidationJob(pollPath, { timeoutMs = 0, intervalMs = 400, onPoll } = {}) {
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
    if (typeof onPoll === 'function') onPoll(payload)
    if (payload.status === 'completed' && payload.result) return normalizeValidateResult(payload.result)
    if (payload.status === 'failed') {
      throw new Error(formatJobError(payload.message || payload.error))
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
  throw new Error('Timed out waiting for validation job to finish')
}

export function ValidationPanel() {
  const navigate = useNavigate()
  const [sourcePath, setSourcePath] = useState('')
  const [targetPath, setTargetPath] = useState('')
  const [fileFormat, setFileFormat] = useState('csv')
  const [uidColumn, setUidColumn] = useState('id')
  const [delimiter, setDelimiter] = useState('auto')
  const [phase, setPhase] = useState('idle')
  const [elapsedMs, setElapsedMs] = useState(0)
  const [result, setResult] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [jobProgress, setJobProgress] = useState({ phase: 'queued', jobId: null, message: '', progress: {} })
  const running = phase === 'running'

  useEffect(() => {
    if (!running) return
    const start = performance.now()
    const id = setInterval(() => setElapsedMs(Math.round(performance.now() - start)), 100)
    return () => clearInterval(id)
  }, [running])

  async function executeValidation() {
    setPhase('running')
    setElapsedMs(0)
    setResult(null)
    setErrorMessage('')
    setJobProgress({ phase: 'queued', jobId: null, message: '', progress: {} })

    try {
      const res = await fetch(absoluteApiUrl('/api/v1/validate/local'), {
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
              },
        ),
      })

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
    } catch (err) {
      setPhase('error')
      setErrorMessage(formatJobError(err instanceof Error ? err.message : String(err)))
    }
  }

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <Card style={{ borderRadius: 24, borderColor: '#F1F1F1', boxShadow: '0 12px 40px rgba(235,76,76,0.10)' }} styles={{ body: { padding: 24 } }}>
        <Typography.Paragraph style={{ marginBottom: 20, textAlign: 'center', color: '#475569' }}>
          Select source and target files on the server to run comparison.
        </Typography.Paragraph>

        <Space direction="vertical" size={20} style={{ width: '100%' }}>
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Typography.Text strong>File format</Typography.Text>
            <Select
              value={fileFormat}
              disabled={running}
              onChange={(value) => setFileFormat(value)}
              style={{ width: 240 }}
              options={[
                { value: 'csv', label: 'CSV / delimited' },
                { value: 'json', label: 'JSON document' },
              ]}
            />
          </Space>

          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <LocalPathBrowser
              label={fileFormat === 'json' ? 'Source JSON (expected)' : 'Source CSV (expected)'}
              value={sourcePath}
              onChange={setSourcePath}
              disabled={running}
            />
            <LocalPathBrowser
              label={fileFormat === 'json' ? 'Target JSON (actual)' : 'Target CSV (actual)'}
              value={targetPath}
              onChange={setTargetPath}
              disabled={running}
            />
          </Space>

          {fileFormat === 'json' ? (
            <Typography.Text type="secondary">
              JSON files are compared as whole documents with sorted keys and sorted array elements (order-insensitive).
            </Typography.Text>
          ) : (
            <Row gutter={16}>
              <Col xs={24} md={14}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Typography.Text strong>UID column</Typography.Text>
                  <Input
                type="text"
                value={uidColumn}
                disabled={running}
                onChange={(ev) => setUidColumn(ev.target.value)}
                autoComplete="off"
                placeholder="e.g. id"
                  />
                </Space>
              </Col>
              <Col xs={24} md={10}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Typography.Text strong>Delimiter</Typography.Text>
                  <Input
                type="text"
                value={delimiter}
                disabled={running}
                onChange={(ev) => setDelimiter(ev.target.value)}
                title="Use auto, tab, \\t, single-char (, ; |), or multi-char (||, ::)"
                aria-label="CSV delimiter or auto"
                placeholder="auto"
                  />
                  <Typography.Text type="secondary">
                    Recommended: <Typography.Text code>auto</Typography.Text>. You can also use <Typography.Text code>tab</Typography.Text>, <Typography.Text code>\t</Typography.Text>, <Typography.Text code>|</Typography.Text>, <Typography.Text code>||</Typography.Text>, <Typography.Text code>::</Typography.Text>.
                  </Typography.Text>
                </Space>
              </Col>
            </Row>
          )}

          <Button
            type="button"
            type="primary"
            disabled={
              running
              || !sourcePath.trim()
              || !targetPath.trim()
              || (fileFormat !== 'json' && !uidColumn.trim())
            }
            onClick={() => { void executeValidation() }}
            style={{ width: '100%', height: 52, borderRadius: 14, background: '#EB4C4C', boxShadow: '0 12px 30px rgba(235,76,76,0.28)' }}
          >
            {running ? (
              <Space>
                <span style={{ width: 20, height: 20, borderRadius: '50%', border: '2px solid rgba(255,253,239,0.4)', borderTopColor: '#FFFDEF', animation: 'spin 1s linear infinite' }} aria-hidden />
                Running...
              </Space>
            ) : (
              'Run validation'
            )}
          </Button>
        </Space>
      </Card>

      <Space direction="vertical" size={16} style={{ width: '100%' }} role="status" aria-live="polite">
        {running ? (
          <ValidationJobProgress
            phase={jobProgress.phase}
            jobId={jobProgress.jobId}
            message={jobProgress.message}
            progress={jobProgress.progress}
            elapsedLabel={`${(elapsedMs / 1000).toFixed(1)}s elapsed`}
          />
        ) : null}

        {phase === 'success' && result ? (
          <Card style={{ borderRadius: 24, borderColor: '#86EFAC', background: '#F0FDF4' }} styles={{ body: { padding: 24 } }}>
            <Typography.Title level={4} style={{ marginTop: 0, color: '#166534' }}>Finished</Typography.Title>
            <Typography.Text style={{ display: 'block', marginBottom: 12, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#334155' }}>Summary of the search</Typography.Text>

            <Row gutter={16} style={{ marginBottom: 20 }}>
              <Col xs={24} sm={12} xl={6}><Card size="small"><Typography.Text type="secondary">Fully Match</Typography.Text><Typography.Title level={2} style={{ marginBottom: 0 }}>{result.summary?.is_match ? 'Yes' : 'No'}</Typography.Title></Card></Col>
              <Col xs={24} sm={12} xl={6}><Card size="small"><Typography.Text type="secondary">Source rows</Typography.Text><Typography.Title level={2} style={{ marginBottom: 0 }}>{result.summary?.source_row_count ?? '-'}</Typography.Title></Card></Col>
              <Col xs={24} sm={12} xl={6}><Card size="small"><Typography.Text type="secondary">Target rows</Typography.Text><Typography.Title level={2} style={{ marginBottom: 0 }}>{result.summary?.target_row_count ?? '-'}</Typography.Title></Card></Col>
              <Col xs={24} sm={12} xl={6}><Card size="small"><Typography.Text type="secondary">Mismatch records</Typography.Text><Typography.Title level={2} style={{ marginBottom: 0 }}>{result.summary?.total_mismatch_records ?? '-'}</Typography.Title></Card></Col>
            </Row>

            <Typography.Text style={{ display: 'block', marginBottom: 12, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#334155' }}>Mismatch counts</Typography.Text>
            <Row gutter={16}>
              <Col xs={24} sm={12} xl={8}><Card size="small"><Typography.Text type="secondary">Missing in Target</Typography.Text><Typography.Title level={3} style={{ marginBottom: 0 }}>{result.mismatch_counts?.missing_in_target ?? 0}</Typography.Title></Card></Col>
              <Col xs={24} sm={12} xl={8}><Card size="small"><Typography.Text type="secondary">Extra in Target</Typography.Text><Typography.Title level={3} style={{ marginBottom: 0 }}>{result.mismatch_counts?.extra_in_target ?? 0}</Typography.Title></Card></Col>
              <Col xs={24} sm={12} xl={8}><Card size="small"><Typography.Text type="secondary">Value Mismatched</Typography.Text><Typography.Title level={3} style={{ marginBottom: 0 }}>{result.mismatch_counts?.value_mismatch ?? 0}</Typography.Title></Card></Col>
            </Row>

            {result.run_id ? <Typography.Paragraph style={{ marginTop: 16, marginBottom: 0, color: '#334155' }}>Run id: <Typography.Text code>{result.run_id}</Typography.Text></Typography.Paragraph> : null}
            {result.durations?.validation_seconds != null ? (
              <Typography.Paragraph style={{ color: '#334155' }}>
                Validation time: <strong>{formatDuration(result.durations.validation_seconds)}</strong>
              </Typography.Paragraph>
            ) : null}

            <Button
              type="button"
              onClick={() => navigate('/report', { state: { result } })}
              type="primary"
              style={{ marginTop: 20, width: '100%', height: 52, borderRadius: 14, background: '#EB4C4C' }}
            >
              View Detailed Report
            </Button>
          </Card>
        ) : null}

        {phase === 'error' ? (
          <Alert type="error" showIcon message="Something went wrong" description={errorMessage} />
        ) : null}
      </Space>

    </Space>
  )
}