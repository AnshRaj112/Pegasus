import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatJobError } from '../../api/formatError.js'
import StepIndicator    from './StepIndicator'
import Step1_DataSource from './Step1_DataSource'
import Step2_FilePicker from './Step2_FilePicker'
import Step3_Configure  from './Step3_Configure'
import StepInputLayout from './StepInputLayout'
import StepFilePairing from './StepFilePairing'
import StepBatchMappingMode from './StepBatchMappingMode'
import ActionBar        from './ActionBar'
import ParallelValidationModal from '../ParallelValidationModal'
import { buildMappingRows, mappingRowFromApi, toColumnMappingPayload } from './columnMapping'
import { buildAnalyzePayload, formatCheckBySource } from './mappingAnalyze'
import MappingColumnPreview from './MappingColumnPreview'
import ResolvedDelimiterNotice from './ResolvedDelimiterNotice'
import { saveValidationDraft } from '../../api/validationHistory'
import {
  buildBatchValidatePayload,
  matchFilePairs,
  newUnitId,
  normalizeBatchPollResult,
  unitFromMerge,
  unitsFromPairs,
} from '../../api/batchValidation'
import { matchCloudFilePairs } from '../../api/cloudBrowse'
import { listAdminCloudConnections } from '../../api/adminCloudConnections'
import {
  applyTemplateToAllUnits,
  buildCsvTemplateSnapshot,
  buildFixedWidthTemplateSnapshot,
  buildJsonTemplateSnapshot,
} from '../../api/batchColumnMapping'


const apiBase = import.meta.env.VITE_API_BASE ?? ''
const pollTimeoutRaw = Number(import.meta.env.VITE_VALIDATION_POLL_TIMEOUT_MS ?? 0)
const pollTimeoutMs  = Number.isFinite(pollTimeoutRaw) ? pollTimeoutRaw : 0

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
  if (Array.isArray(detail)) return detail.map(e => (typeof e === 'object' && e != null ? e.msg ?? e.message : null) ?? JSON.stringify(e)).join('; ')
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

function normalizeResult(data) {
  if (!data) return data
  if ((data.mismatch_samples?.length ?? 0) > 0) return data
  const flattened = flattenMismatchSampleGroups(data.mismatch_sample_groups)
  if (flattened.length === 0) return data
  return { ...data, mismatch_samples: flattened }
}

const DEFAULT_CLOUD_CONFIG = {
  provider: 'google-cloud-storage',
  connectionId: '',
  bucket: '',
  objectName: '',
  credentialsJson: '',
  projectId: '',
}

function isCsvLikeFormat(fileFormat) {
  return fileFormat === 'csv' || fileFormat === 'zip' || fileFormat === 'dat'
}

function backendFileFormat(fileFormat) {
  return fileFormat === 'zip' || fileFormat === 'dat' ? 'csv' : fileFormat
}

function pickDefaultUidColumn(columns, hasHeader) {
  if (!Array.isArray(columns) || columns.length === 0) return ''
  if (hasHeader) {
    for (const name of ['id', 'uid', 'line', 'key', 'code']) {
      if (columns.includes(name)) return name
    }
  } else if (columns.includes('column_1')) {
    return 'column_1'
  }
  return columns[0]
}

function describeStorageInput(storageType, path, cloudConfig) {
  if (storageType === 'cloud') {
    const bucket = String(cloudConfig?.bucket || '').trim()
    const objectName = String(cloudConfig?.objectName || '').trim()
    if (bucket && objectName) return `gs://${bucket}/${objectName}`
    if (bucket) return `gs://${bucket}/...`
    return 'Google Cloud Storage'
  }
  return path || '—'
}

function normalizeGcsObjectName(bucket, raw) {
  let name = String(raw || '').trim()
  if (!name) return ''
  if (name.startsWith('gs://')) {
    const withoutScheme = name.slice(5)
    const slash = withoutScheme.indexOf('/')
    name = slash >= 0 ? withoutScheme.slice(slash + 1) : ''
  }
  const bucketName = String(bucket || '').trim()
  if (bucketName && name.startsWith(`${bucketName}/`)) {
    name = name.slice(bucketName.length + 1)
  }
  return name
}

function resolveCloudConfig(cloudConfig, savedConnections = []) {
  const bucket = String(cloudConfig?.bucket || '').trim()
  const objectName = normalizeGcsObjectName(bucket, cloudConfig?.objectName)
  let connectionId = String(cloudConfig?.connectionId || '').trim()
  let credentialsJson = String(cloudConfig?.credentialsJson || '').trim()
  let projectId = String(cloudConfig?.projectId || '').trim()
  if (!connectionId && !credentialsJson && bucket) {
    const match = savedConnections.find((row) => String(row.bucket || '').trim() === bucket)
    if (match) {
      connectionId = String(match.id)
      if (!projectId) projectId = String(match.project_id || '').trim()
    }
  }
  return {
    provider: String(cloudConfig?.provider || 'google-cloud-storage').trim() || 'google-cloud-storage',
    connectionId,
    bucket,
    objectName,
    credentialsJson,
    projectId,
  }
}

function buildStoragePayload(prefix, storageType, path, cloudConfig, savedConnections = []) {
  if (storageType === 'cloud') {
    const resolved = resolveCloudConfig(cloudConfig, savedConnections)
    return {
      [`${prefix}_cloud`]: {
        provider: resolved.provider,
        connection_id: resolved.connectionId || undefined,
        bucket: resolved.bucket || undefined,
        object_name: resolved.objectName,
        credentials_json: resolved.credentialsJson || undefined,
        project_id: resolved.projectId || undefined,
      },
    }
  }
  return { [`${prefix}_path`]: String(path || '').trim() }
}

function isStorageSelectionComplete(storageType, path, cloudConfig, savedConnections = []) {
  if (storageType === 'cloud') {
    const resolved = resolveCloudConfig(cloudConfig, savedConnections)
    return Boolean(
      resolved.bucket
      && resolved.objectName
      && (resolved.credentialsJson || resolved.connectionId),
    )
  }
  return Boolean(String(path || '').trim())
}

function cloudSelectionError(side, storageType, path, cloudConfig, savedConnections = []) {
  if (storageType !== 'cloud') {
    return String(path || '').trim() ? '' : `Please specify a ${side} path.`
  }
  const resolved = resolveCloudConfig(cloudConfig, savedConnections)
  if (!resolved.bucket) return `Please specify a ${side} bucket.`
  if (!resolved.objectName) return `Please specify a ${side} object path.`
  if (!resolved.connectionId && !resolved.credentialsJson) {
    return `Select a saved cloud connection for ${side}, or paste service account JSON.`
  }
  return ''
}

async function pollJobDetail(pollPath, { timeoutMs = 0, intervalMs = 400, onPoll } = {}) {
  const url = absoluteApiUrl(pollPath)
  const deadline = timeoutMs > 0 ? Date.now() + timeoutMs : Number.POSITIVE_INFINITY
  while (Date.now() < deadline) {
    const res = await fetch(url, { method: 'GET' })
    const raw = await res.text()
    let payload = {}
    if (raw) { try { payload = JSON.parse(raw) } catch { throw new Error(raw.trim().slice(0, 400)) } }
    if (!res.ok) throw new Error(formatDetail(payload.detail) || `${res.status} ${res.statusText}`)
    if (typeof onPoll === 'function') onPoll(payload)
    if (payload.status === 'completed') {
      if (payload.batch_result) return payload
      if (payload.result) return { ...payload, result: normalizeResult(payload.result) }
      return payload
    }
    if (payload.status === 'failed') {
      throw new Error(formatJobError(payload.message || payload.error))
    }
    await new Promise(r => setTimeout(r, intervalMs))
  }
  throw new Error('Timed out waiting for validation job')
}

async function pollJob(pollPath, { timeoutMs = 0, intervalMs = 400, onPoll } = {}) {
  const url = absoluteApiUrl(pollPath)
  const deadline = timeoutMs > 0 ? Date.now() + timeoutMs : Number.POSITIVE_INFINITY
  while (Date.now() < deadline) {
    const res = await fetch(url, { method: 'GET' })
    const raw = await res.text()
    let payload = {}
    if (raw) { try { payload = JSON.parse(raw) } catch { throw new Error(raw.trim().slice(0, 400)) } }
    if (!res.ok) throw new Error(formatDetail(payload.detail) || `${res.status} ${res.statusText}`)
    if (typeof onPoll === 'function') onPoll(payload)
    if (payload.status === 'completed' && payload.result) return normalizeResult(payload.result)
    if (payload.status === 'failed') {
      throw new Error(formatJobError(payload.message || payload.error))
    }
    await new Promise(r => setTimeout(r, intervalMs))
  }
  throw new Error('Timed out waiting for validation job')
}

/* ── Stat card sub-component ────────────────────────────────── */
function StatCard({ label, value, accent }) {
  return (
    <div style={{
      padding: '10px 14px', borderRadius: 9,
      background: 'var(--surface-2)', border: '1px solid var(--border-1)',
    }}>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'Geist Mono, monospace', color: accent ?? 'var(--text-1)', letterSpacing: '-0.02em' }}>
        {String(value)}
      </div>
    </div>
  )
}

function buildFixedWidthValidateConfig({
  columns,
  joinColumn,
  matchStrategy,
  dateColumn,
  sourceDateStart,
  sourceDateEnd,
  sourceDateFormat,
  targetDateStart,
  targetDateEnd,
  targetDateFormat,
}) {
  const join = columns.find(c => c.field_name === joinColumn)
  const fields = columns.map(col => {
    const isDate = col.field_name === dateColumn
    return {
      field_name: col.field_name,
      source_start: Number(col.source_start),
      source_end: Number(col.source_end),
      target_start: Number(col.target_start),
      target_end: Number(col.target_end),
      field_type: isDate ? 'date' : 'text',
      ...(isDate
        ? {
            source_date_format: sourceDateFormat.trim(),
            target_date_format: targetDateFormat.trim(),
          }
        : {}),
    }
  })
  return {
    uid_column: joinColumn,
    uid_source_start: join ? Number(join.source_start) : 0,
    uid_source_end: join ? Number(join.source_end) : 0,
    uid_target_start: join ? Number(join.target_start) : 0,
    uid_target_end: join ? Number(join.target_end) : 0,
    fields,
    match_strategy: matchStrategy,
    fuzzy_similarity_threshold: 0.75,
    source_date_start: sourceDateStart,
    source_date_end: sourceDateEnd,
    source_date_format: sourceDateFormat.trim(),
    target_date_start: targetDateStart,
    target_date_end: targetDateEnd,
    target_date_format: targetDateFormat.trim(),
  }
}

function FixedWidthConfigurator({
  sourcePath,
  targetPath,
  columns,
  setColumns,
  joinColumn,
  setJoinColumn,
  matchStrategy,
  setMatchStrategy,
  dateColumn,
    setDateColumn,
  layoutLoading,
  layoutError,
  sourceDateStart,
  setSourceDateStart,
  sourceDateEnd,
  setSourceDateEnd,
  sourceDateFormat,
  setSourceDateFormat,
  targetDateStart,
  setTargetDateStart,
  targetDateEnd,
  setTargetDateEnd,
  targetDateFormat,
  setTargetDateFormat,
  sourceSample,
  targetSample,
}) {
  return (
    <div style={{ animation: 'fade-in 0.25s ease' }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
          Step 2 of 3
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 6 }}>
          Configure Fixed-Width Validation
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)', maxWidth: 760 }}>
          Columns are detected from your files. Choose which column should <strong>match rows</strong> between source
          and target (the target may be unsorted). All other columns are compared on that basis.
          Use <strong>Similar keys</strong> when typos or rearrangements happen (e.g. username <code style={{ fontFamily: 'monospace' }}>abc</code> vs <code style={{ fontFamily: 'monospace' }}>bca</code>) — those appear as value mismatches, not missing/extra rows.
        </p>
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 20,
        padding: '12px 14px', borderRadius: 10,
        background: 'var(--surface-2)', border: '1px solid var(--border-1)',
      }}>
        {[{ label: 'Source File', path: sourcePath }, { label: 'Target File', path: targetPath }].map(({ label, path }) => (
          <div key={label}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 4 }}>
              {label}
            </div>
            <code style={{
              display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              fontSize: 11, color: 'var(--text-2)',
              fontFamily: 'Geist Mono, monospace',
            }} title={path}>
              {path || '—'}
            </code>
          </div>
        ))}
      </div>

      {layoutLoading ? (
        <p style={{ fontSize: 13, color: 'var(--text-3)', marginBottom: 16 }}>Detecting columns…</p>
      ) : null}
      {layoutError ? (
        <p style={{ fontSize: 13, color: 'var(--danger)', marginBottom: 16 }}>{layoutError}</p>
      ) : null}

      {(sourceSample || targetSample) ? (
        <div style={{
          marginBottom: 16, padding: '10px 12px', borderRadius: 8,
          background: 'var(--surface-2)', border: '1px solid var(--border-1)', fontSize: 11,
          fontFamily: 'Geist Mono, monospace', color: 'var(--text-3)',
        }}>
          <div style={{ marginBottom: 4 }}><span style={{ color: 'var(--text-4)' }}>Source sample: </span>{sourceSample || '—'}</div>
          <div><span style={{ color: 'var(--text-4)' }}>Target sample: </span>{targetSample || '—'}</div>
        </div>
      ) : null}

      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20,
        padding: 16, borderRadius: 12, background: 'var(--surface-1)', border: '1px solid var(--border-1)',
      }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)' }}>Match rows by column</span>
          <select
            value={joinColumn}
            onChange={e => setJoinColumn(e.target.value)}
            className="input"
            style={{ height: 36 }}
          >
            {columns.map(col => (
              <option key={col.field_name} value={col.field_name}>{col.field_name}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)' }}>Row matching mode</span>
          <select
            value={matchStrategy}
            onChange={e => setMatchStrategy(e.target.value)}
            className="input"
            style={{ height: 36 }}
          >
            <option value="exact">Exact key — join values must match exactly</option>
            <option value="fuzzy">Similar keys — typos / anagrams pair as mismatches</option>
          </select>
        </label>
      </div>

      {columns.length > 0 ? (
        <div style={{
          marginBottom: 20, borderRadius: 12, border: '1px solid var(--border-1)',
          overflow: 'hidden', background: 'var(--surface-1)',
        }}>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--surface-2)', textAlign: 'left' }}>
                <th style={{ padding: '8px 10px' }}>Column</th>
                <th style={{ padding: '8px 10px' }}>Src start</th>
                <th style={{ padding: '8px 10px' }}>Src end</th>
                <th style={{ padding: '8px 10px' }}>Tgt start</th>
                <th style={{ padding: '8px 10px' }}>Tgt end</th>
                <th style={{ padding: '8px 10px' }}>Date field</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((col, i) => (
                <tr key={col.field_name} style={{ borderTop: '1px solid var(--border-1)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>{col.field_name}</td>
                  {['source_start', 'source_end', 'target_start', 'target_end'].map(key => (
                    <td key={key} style={{ padding: '6px 8px' }}>
                      <input
                        type="number"
                        min={0}
                        value={col[key]}
                        onChange={e => {
                          const next = [...columns]
                          next[i] = { ...col, [key]: Number(e.target.value) || 0 }
                          setColumns(next)
                          if (col.field_name === dateColumn && key === 'source_start') setSourceDateStart(Number(e.target.value) || 0)
                          if (col.field_name === dateColumn && key === 'source_end') setSourceDateEnd(Number(e.target.value) || 0)
                          if (col.field_name === dateColumn && key === 'target_start') setTargetDateStart(Number(e.target.value) || 0)
                          if (col.field_name === dateColumn && key === 'target_end') setTargetDateEnd(Number(e.target.value) || 0)
                        }}
                        className="input input-mono"
                        style={{ width: '100%', height: 30, fontSize: 11 }}
                      />
                    </td>
                  ))}
                  <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                    <input
                      type="radio"
                      name="fw-date-col"
                      checked={dateColumn === col.field_name}
                      onChange={() => {
                        setDateColumn(col.field_name)
                        setSourceDateStart(Number(col.source_start))
                        setSourceDateEnd(Number(col.source_end))
                        setTargetDateStart(Number(col.target_start))
                        setTargetDateEnd(Number(col.target_end))
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div style={{
          background: 'var(--surface-1)',
          border: '1px solid var(--border-1)',
          borderRadius: 12,
          padding: 20,
          boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
        }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)' }} />
            Source date format ({dateColumn || '—'})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <label>
              <span style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-2)', marginBottom: 6 }}>
                Character Start Position (0-indexed)
              </span>
              <input
                type="number"
                min={0}
                value={sourceDateStart}
                onChange={e => setSourceDateStart(Number(e.target.value) || 0)}
                className="input input-mono"
                style={{ width: '100%', height: 36, fontSize: 12 }}
              />
            </label>
            <label>
              <span style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-2)', marginBottom: 6 }}>
                Character End Position (exclusive)
              </span>
              <input
                type="number"
                min={0}
                value={sourceDateEnd}
                onChange={e => setSourceDateEnd(Number(e.target.value) || 0)}
                className="input input-mono"
                style={{ width: '100%', height: 36, fontSize: 12 }}
              />
            </label>
            <label>
              <span style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-2)', marginBottom: 6 }}>
                Date Format
              </span>
              <input
                type="text"
                value={sourceDateFormat}
                onChange={e => setSourceDateFormat(e.target.value)}
                placeholder="dd-mm-yyyy or %d-%m-%Y"
                className="input input-mono"
                style={{ width: '100%', height: 36, fontSize: 12 }}
              />
              <span style={{ display: 'block', fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>
                Example: <code style={{ fontFamily: 'monospace' }}>dd-mm-yyyy</code> or <code style={{ fontFamily: 'monospace' }}>%d-%m-%Y</code> for 19-05-2026
              </span>
            </label>
          </div>
        </div>

        {/* Target Configuration */}
        <div style={{
          background: 'var(--surface-1)',
          border: '1px solid var(--border-1)',
          borderRadius: 12,
          padding: 20,
          boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
        }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--blue, #3b82f6)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--blue, #3b82f6)' }} />
            Target date format ({dateColumn || '—'})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <label>
              <span style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-2)', marginBottom: 6 }}>
                Character Start Position (0-indexed)
              </span>
              <input
                type="number"
                min={0}
                value={targetDateStart}
                onChange={e => setTargetDateStart(Number(e.target.value) || 0)}
                className="input input-mono"
                style={{ width: '100%', height: 36, fontSize: 12 }}
              />
            </label>
            <label>
              <span style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-2)', marginBottom: 6 }}>
                Character End Position (exclusive)
              </span>
              <input
                type="number"
                min={0}
                value={targetDateEnd}
                onChange={e => setTargetDateEnd(Number(e.target.value) || 0)}
                className="input input-mono"
                style={{ width: '100%', height: 36, fontSize: 12 }}
              />
            </label>
            <label>
              <span style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-2)', marginBottom: 6 }}>
                Date Format
              </span>
              <input
                type="text"
                value={targetDateFormat}
                onChange={e => setTargetDateFormat(e.target.value)}
                placeholder="mm-dd-yyyy or %m-%d-%Y"
                className="input input-mono"
                style={{ width: '100%', height: 36, fontSize: 12 }}
              />
              <span style={{ display: 'block', fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>
                Example: <code style={{ fontFamily: 'monospace' }}>mm-dd-yyyy</code> or <code style={{ fontFamily: 'monospace' }}>%m-%d-%Y</code> for 05-19-2026
              </span>
            </label>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function MappingWizard({ initialMappingData, onResetInitialData }) {
  const navigate = useNavigate()
  const [step, setStep]         = useState(1)
  const [subPhase, setSubPhase] = useState('unified-selection')
  const [sourceStorageType, setSourceStorageType] = useState('local')
  const [targetStorageType, setTargetStorageType] = useState('local')
  const [sourcePath, setSourcePath] = useState('')
  const [targetPath, setTargetPath] = useState('')
  const [sourceCloudConfig, setSourceCloudConfig] = useState(DEFAULT_CLOUD_CONFIG)
  const [targetCloudConfig, setTargetCloudConfig] = useState(DEFAULT_CLOUD_CONFIG)
  const [savedCloudConnections, setSavedCloudConnections] = useState([])
  const [fileFormat, setFileFormat] = useState('csv')

  // Redesign state variables
  const [isBrowserOpen, setIsBrowserOpen] = useState(false)
  const [browserTarget, setBrowserTarget] = useState('source')
  const [isFormatPopupOpen, setIsFormatPopupOpen] = useState(false)
  const [isManualFormat, setIsManualFormat] = useState(false)
  const [pendingTransition, setPendingTransition] = useState(false)
  const [sourceDateStart, setSourceDateStart] = useState(58)
  const [sourceDateEnd, setSourceDateEnd] = useState(68)
  const [sourceDateFormat, setSourceDateFormat] = useState('dd/mm/yyyy')
  const [targetDateStart, setTargetDateStart] = useState(58)
  const [targetDateEnd, setTargetDateEnd] = useState(68)
  const [targetDateFormat, setTargetDateFormat] = useState('yyyy/mm/dd')
  const [fwColumns, setFwColumns] = useState([])
  const [fwJoinColumn, setFwJoinColumn] = useState('name')
  const [fwMatchStrategy, setFwMatchStrategy] = useState('fuzzy')
  const [fwDateColumn, setFwDateColumn] = useState('dob')
  const [fwLayoutLoading, setFwLayoutLoading] = useState(false)
  const [fwLayoutError, setFwLayoutError] = useState('')
  const [fwSourceSample, setFwSourceSample] = useState('')
  const [fwTargetSample, setFwTargetSample] = useState('')
  const [mappings, setMappings]   = useState([])
  const [uidColumn, setUidColumn] = useState('id')
  const [delimiter, setDelimiter] = useState('auto')
  const [hasHeader, setHasHeader] = useState(true)

  const [columnPreview, setColumnPreview] = useState({
    sourceColumns: [],
    targetColumns: [],
    compareColumns: [],
    autoMappings: [],
    unmatchedSourceColumns: [],
    unmatchedTargetColumns: [],
    delimiter: 'auto',
    sourceSamples: {},
    targetSamples: {},
    sampleRowCount: 6,
  })

  const [columnPreviewLoading, setColumnPreviewLoading] = useState(false)
  const [columnPreviewError, setColumnPreviewError] = useState('')
  const [validateHeaderFormats, setValidateHeaderFormats] = useState(false)
  const [validateFooters, setValidateFooters] = useState(false)
  const [headerLeadingRows, setHeaderLeadingRows] = useState(0)
  const [footerTrailingRows, setFooterTrailingRows] = useState(1)
  const [testMode, setTestMode] = useState('full')
  const [uidGte, setUidGte] = useState('')
  const [formatChecks, setFormatChecks] = useState([])
  const [footerValidation, setFooterValidation] = useState(null)
  const [analyzeLoading, setAnalyzeLoading] = useState(false)
  const [analyzeError, setAnalyzeError] = useState('')

  useEffect(() => {
    async function loadSavedCloudConnections() {
      try {
        const rows = await listAdminCloudConnections()
        setSavedCloudConnections(Array.isArray(rows) ? rows : [])
      } catch {
        setSavedCloudConnections([])
      }
    }
    loadSavedCloudConnections()
  }, [])

  const [parallelModalOpen, setParallelModalOpen] = useState(false)
  const [isRunning, setIsRunning]   = useState(false)
  const [result, setResult]         = useState(null)
  const [errorMsg, setErrorMsg]     = useState('')
  const [phase, setPhase]           = useState('idle')
  const [jobProgress, setJobProgress] = useState({ phase: 'queued', jobId: null })

  const [draftSaveStatus, setDraftSaveStatus] = useState('idle')
  const [draftSaveError, setDraftSaveError] = useState('')
  const preserveFixedWidthDatesRef = useRef(false)

  const [inputLayout, setInputLayout] = useState('pair')
  const [onUnitFailure, setOnUnitFailure] = useState('continue')
  const [validationUnits, setValidationUnits] = useState([])
  const [activeUnitId, setActiveUnitId] = useState(null)
  const [unitConfigs, setUnitConfigs] = useState({})
  const [batchResult, setBatchResult] = useState(null)
  const [pairingState, setPairingState] = useState({ pairs: [], unmatchedSources: [], unmatchedTargets: [] })
  const [sourceFolder, setSourceFolder] = useState('')
  const [targetFolder, setTargetFolder] = useState('')
  const [sourceMultiPaths, setSourceMultiPaths] = useState([])
  const [targetMultiPaths, setTargetMultiPaths] = useState([])
  const [pairingLoading, setPairingLoading] = useState(false)
  const [pairingError, setPairingError] = useState('')
  const [recursiveFolderMatch, setRecursiveFolderMatch] = useState(false)
  const [sourceCloudPrefix, setSourceCloudPrefix] = useState('')
  const [targetCloudPrefix, setTargetCloudPrefix] = useState('')
  const [batchColumnMappingMode, setBatchColumnMappingMode] = useState('choose')
  const [batchMismatchUnitIds, setBatchMismatchUnitIds] = useState([])
  const [batchMismatchDetails, setBatchMismatchDetails] = useState({})
  const [batchApplyAllLoading, setBatchApplyAllLoading] = useState(false)
  const [batchApplyAllError, setBatchApplyAllError] = useState('')

  const isBatchMode = inputLayout !== 'pair'
  const apiFileFormat = backendFileFormat(fileFormat)
  const multiPairBatch = isBatchMode && validationUnits.length > 1
    && (isCsvLikeFormat(fileFormat) || fileFormat === 'fixed-width' || fileFormat === 'json')
  const mappingQueueUnits = batchColumnMappingMode === 'template-fixups'
    ? validationUnits.filter(u => batchMismatchUnitIds.includes(u.unitId))
    : validationUnits
  const activeUnit = validationUnits.find(u => u.unitId === activeUnitId)
    || mappingQueueUnits.find(u => u.unitId === activeUnitId)
    || (activeUnitId == null && batchColumnMappingMode === 'choose' ? null : validationUnits[0])
    || null
  const effectiveSourcePath = isBatchMode
    ? (activeUnit?.sourcePaths?.[0] || '')
    : (sourceStorageType === 'cloud' ? sourceCloudConfig.objectName : sourcePath)
  const effectiveTargetPath = isBatchMode
    ? (activeUnit?.targetPaths?.[0] || '')
    : (targetStorageType === 'cloud' ? targetCloudConfig.objectName : targetPath)

  useEffect(() => {
    let cancelled = false
    async function loadSavedCloudConnections() {
      try {
        const rows = await listAdminCloudConnections()
        if (!cancelled) setSavedCloudConnections(Array.isArray(rows) ? rows : [])
      } catch {
        if (!cancelled) setSavedCloudConnections([])
      }
    }
    loadSavedCloudConnections()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!initialMappingData) return

    const { detail, preview, step: targetStep, error } = initialMappingData
    preserveFixedWidthDatesRef.current = targetStep === 4
      && (detail.delimiter === 'fixed-width' || detail.delimiter === 'fixed')

    // Initialize configuration states from detail
    setSourceStorageType('local')
    setTargetStorageType('local')
    setSourceCloudConfig(DEFAULT_CLOUD_CONFIG)
    setTargetCloudConfig(DEFAULT_CLOUD_CONFIG)
    setSourcePath(detail.source_path || detail.source_filename || '')
    setTargetPath(detail.target_path || detail.target_filename || '')
    setValidateHeaderFormats(detail.validate_header_formats || false)
    setValidateFooters(detail.validate_footers || false)
    setHeaderLeadingRows(detail.header_leading_rows || 0)
    setFooterTrailingRows(detail.footer_trailing_rows || 1)
    setTestMode(detail.test_mode || 'full')
    setUidGte(detail.uid_gte || '')

    if (detail.delimiter === 'fixed-width' || detail.delimiter === 'fixed') {
      setFileFormat('fixed-width')
      const saved = detail.column_mappings || []
      const getVal = (name) => saved.find(m => m.source_column === name)?.target_column || ''
      setSourceDateStart(Number(getVal('source_date_start')) || 58)
      setSourceDateEnd(Number(getVal('source_date_end')) || 68)
      setSourceDateFormat(getVal('source_date_format') || 'dd/mm/yyyy')
      setTargetDateStart(Number(getVal('target_date_start')) || 58)
      setTargetDateEnd(Number(getVal('target_date_end')) || 68)
      setTargetDateFormat(getVal('target_date_format') || 'yyyy/mm/dd')
    } else {
      setFileFormat('csv')
      setUidColumn(detail.uid_column || 'id')
      setDelimiter(detail.delimiter || 'auto')
      setHasHeader(detail.has_header !== false)
    }

    // Load previews
    if (preview && detail.delimiter !== 'fixed-width' && detail.delimiter !== 'fixed') {
      setColumnPreview({
        sourceColumns: preview.source_columns || [],
        targetColumns: preview.target_columns || [],
        compareColumns: preview.compare_columns || [],
        autoMappings: preview.auto_mappings || [],
        unmatchedSourceColumns: preview.unmatched_source_columns || [],
        unmatchedTargetColumns: preview.unmatched_target_columns || [],
        delimiter: preview.delimiter || 'auto',
        sourceSamples: preview.source_samples || {},
        targetSamples: preview.target_samples || {},
        sampleRowCount: preview.sample_row_count || 6,
      })
      if (typeof preview.inferred_has_header === 'boolean') {
        setHasHeader(preview.inferred_has_header)
      } else if (typeof preview.has_header === 'boolean') {
        setHasHeader(preview.has_header)
      }
      setColumnPreviewError('')
    } else if (error) {
      setColumnPreviewError(error)
    }

    // Populate customized mappings (use saved detail when live preview is unavailable)
    const savedMappings = detail.column_mappings || []
    if (detail.delimiter !== 'fixed-width' && detail.delimiter !== 'fixed') {
      const uid = (detail.uid_column || 'id').trim()
      const previousRows = savedMappings.map(m => mappingRowFromApi(m))
      let compareCols = (preview?.compare_columns?.length
        ? preview.compare_columns
        : (detail.compared_columns?.length
          ? detail.compared_columns
          : savedMappings.map(m => m.source_column).filter(col => col && col !== uid)))
      let targetCols = (preview?.target_columns?.length
        ? preview.target_columns.filter(col => col !== uid)
        : [...new Set(savedMappings.map(m => m.target_column).filter(Boolean))])
      if (!compareCols.length && previousRows.length) {
        compareCols = previousRows.map(row => row.sourceCol).filter(Boolean)
      }
      if (!targetCols.length && previousRows.length) {
        targetCols = [...new Set(previousRows.map(row => row.targetCol).filter(Boolean))]
      }
      setMappings(buildMappingRows(compareCols, targetCols, previousRows, preview?.auto_mappings || []))
    }

    // Route step
    if (targetStep === 1 || targetStep === 2) {
      setStep(1)
      setSubPhase('unified-selection')
    } else {
      setStep(targetStep)
      if (targetStep === 4) {
        setSubPhase('type-select')
      }
    }
    if (error) {
      setAnalyzeError(error)
      setColumnPreviewError(error)
    }

    queueMicrotask(() => onResetInitialData())
  }, [initialMappingData, onResetInitialData])



  function detectFormatFromPath(path) {
    if (!path) return null
    if (Array.isArray(path)) {
      if (path.length === 0) return null
      path = path[0]
    }
    const cleanPath = String(path).trim().toLowerCase()
    if (cleanPath.endsWith('.csv') || cleanPath.endsWith('.tsv')) return 'csv'
    if (cleanPath.endsWith('.zip')) return 'zip'
    if (cleanPath.endsWith('.dat')) return 'dat'
    if (cleanPath.endsWith('.json') || cleanPath.endsWith('.jsonl')) return 'json'
    return null
  }

  function autoDetectFormat() {
    let pathsToCheck = []
    if (inputLayout === 'pair') {
      const sourceCandidate = sourceStorageType === 'cloud' ? sourceCloudConfig.objectName : sourcePath
      const targetCandidate = targetStorageType === 'cloud' ? targetCloudConfig.objectName : targetPath
      pathsToCheck = [sourceCandidate, targetCandidate]
    } else if (inputLayout === 'folder') {
      const sourceCandidate = sourceStorageType === 'cloud' ? sourceCloudPrefix : sourceFolder
      const targetCandidate = targetStorageType === 'cloud' ? targetCloudPrefix : targetFolder
      pathsToCheck = [sourceCandidate, targetCandidate]
    } else if (inputLayout === 'source-one-target-many') {
      const sourceCandidate = sourceStorageType === 'cloud' ? sourceCloudConfig.objectName : sourcePath
      pathsToCheck = [sourceCandidate, ...targetMultiPaths]
    } else if (inputLayout === 'source-many-target-one') {
      const targetCandidate = targetStorageType === 'cloud' ? targetCloudConfig.objectName : targetPath
      pathsToCheck = [...sourceMultiPaths, targetCandidate]
    }

    for (const p of pathsToCheck) {
      const detected = detectFormatFromPath(p)
      if (detected) return detected
    }
    return null
  }

  function handleContinue() {
    let err = ''
    if (inputLayout === 'pair') {
      err = cloudSelectionError('Source', sourceStorageType, sourcePath, sourceCloudConfig, savedCloudConnections)
        || cloudSelectionError('Target', targetStorageType, targetPath, targetCloudConfig, savedCloudConnections)
    } else if (inputLayout === 'folder') {
      const sourceFolderValue = sourceStorageType === 'cloud' ? sourceCloudPrefix : sourceFolder
      const targetFolderValue = targetStorageType === 'cloud' ? targetCloudPrefix : targetFolder
      if (!sourceFolderValue.trim()) err = 'Please specify a Source folder.'
      else if (!targetFolderValue.trim()) err = 'Please specify a Target folder.'
    } else if (inputLayout === 'source-one-target-many') {
      err = cloudSelectionError('Source', sourceStorageType, sourcePath, sourceCloudConfig, savedCloudConnections)
      if (!err && targetMultiPaths.length === 0) err = 'Please select at least one Target file.'
    } else if (inputLayout === 'source-many-target-one') {
      if (sourceMultiPaths.length === 0) err = 'Please select at least one Source file.'
      else {
        err = cloudSelectionError('Target', targetStorageType, targetPath, targetCloudConfig, savedCloudConnections)
      }
    }

    if (err) {
      setPairingError(err)
      return
    }
    setPairingError('')
    if (sourceStorageType === 'cloud') {
      setSourceCloudConfig(resolveCloudConfig(sourceCloudConfig, savedCloudConnections))
    }
    if (targetStorageType === 'cloud') {
      setTargetCloudConfig(resolveCloudConfig(targetCloudConfig, savedCloudConnections))
    }

    let format = fileFormat
    if (!isManualFormat) {
      const detected = autoDetectFormat()
      if (detected) {
        format = detected
        setFileFormat(detected)
      } else {
        setPendingTransition(true)
        setIsFormatPopupOpen(true)
        return
      }
    }

    executeTransition(format)
  }

  function executeTransition(format) {
    setPendingTransition(false)
    if (inputLayout === 'pair') {
      setStep(3)
    } else if (inputLayout === 'folder') {
      setStep(2)
      if (sourceStorageType === 'cloud' || targetStorageType === 'cloud') {
        runAutoPairingCloud(sourceCloudPrefix, targetCloudPrefix)
      } else {
        runAutoPairing(sourceFolder, targetFolder)
      }
    } else if (inputLayout === 'source-one-target-many') {
      const unit = unitFromMerge({
        sourcePaths: [sourcePath],
        targetPaths: targetMultiPaths,
        label: `${sourcePath.split('/').pop()} → ${targetMultiPaths.length} targets`,
      })
      setValidationUnits([unit])
      setActiveUnitId(unit.unitId)
      setStep(3)
    } else if (inputLayout === 'source-many-target-one') {
      const unit = unitFromMerge({
        sourcePaths: sourceMultiPaths,
        targetPaths: [targetPath],
        label: `${sourceMultiPaths.length} sources → ${targetPath.split('/').pop()}`,
      })
      setValidationUnits([unit])
      setActiveUnitId(unit.unitId)
      setStep(3)
    }
  }

  function handleSourceBrowserSelect(selection) {
    const parsed = parseSelection(selection)
    if (!parsed) return
    if (parsed.kind === 'cloud') {
      setSourceCloudConfig(resolveCloudConfig({
        provider: parsed.provider || 'google-cloud-storage',
        bucket: parsed.bucket || '',
        objectName: parsed.objectName || '',
        credentialsJson: parsed.credentialsJson || '',
        projectId: parsed.projectId || '',
        connectionId: parsed.connectionId || sourceCloudConfig.connectionId || '',
      }, savedCloudConnections))
      setSourcePath('')
    } else if (parsed.kind === 'cloud-folder') {
      applyCloudConfig(parsed)
      setSourceCloudPrefix(parsed.prefix || '')
    } else if (parsed.kind === 'cloud-files') {
      applyCloudConfig(parsed)
      setSourceMultiPaths(parsed.objectNames || [])
    } else if (inputLayout === 'folder' && parsed.kind === 'folder') {
      setSourceFolder(parsed.path)
    } else if (inputLayout === 'source-many-target-one' && parsed.kind === 'files') {
      setSourceMultiPaths(parsed.paths || [])
    } else if (parsed.kind === 'file' || typeof selection === 'string') {
      setSourcePath(parsed.path || selection)
    }

    if (parsed.path || typeof selection === 'string') {
      const detected = detectFormatFromPath(parsed.path || selection)
      if (detected) {
        setFileFormat(detected)
        setIsManualFormat(false)
      }
    }

    setIsBrowserOpen(false)
  }

  function handleTargetBrowserSelect(selection) {
    const parsed = parseSelection(selection)
    if (!parsed) return
    if (parsed.kind === 'cloud') {
      setTargetCloudConfig(resolveCloudConfig({
        provider: parsed.provider || 'google-cloud-storage',
        bucket: parsed.bucket || '',
        objectName: parsed.objectName || '',
        credentialsJson: parsed.credentialsJson || '',
        projectId: parsed.projectId || '',
        connectionId: parsed.connectionId || targetCloudConfig.connectionId || '',
      }, savedCloudConnections))
      setTargetPath('')
    } else if (parsed.kind === 'cloud-folder') {
      applyCloudConfig(parsed)
      setTargetCloudPrefix(parsed.prefix || '')
    } else if (inputLayout === 'folder' && parsed.kind === 'folder') {
      setTargetFolder(parsed.path)
    } else if (inputLayout === 'source-one-target-many' && parsed.kind === 'files') {
      setTargetMultiPaths(parsed.paths || [])
    } else if (parsed.kind === 'file' || typeof selection === 'string') {
      setTargetPath(parsed.path || selection)
    }

    setIsBrowserOpen(false)
  }

  function handleDataSourceNext(srcType, tgtType) {
    setSourceStorageType(srcType); setTargetStorageType(tgtType)
    if (inputLayout === 'folder') setSubPhase('pick-source-folder')
    else if (inputLayout === 'source-one-target-many') setSubPhase('pick-source')
    else if (inputLayout === 'source-many-target-one') setSubPhase('pick-source-multi')
    else setSubPhase('pick-source')
  }

  function handleInputLayoutNext(layout) {
    setInputLayout(layout)
    setValidationUnits([])
    setActiveUnitId(null)
    setUnitConfigs({})
    setStep(2)
    setSubPhase('type-select')
  }

  function persistActiveUnitConfig() {
    if (!isBatchMode || !activeUnitId) return
    setUnitConfigs(prev => ({
      ...prev,
      [activeUnitId]: {
        mappings,
        uidColumn,
        delimiter,
        hasHeader,
        validateHeaderFormats,
        validateFooters,
        headerLeadingRows,
        footerTrailingRows,
        testMode,
        uidGte,
        columnPreview,
        formatChecks,
        footerValidation,
        fwColumns,
        fwJoinColumn,
        fwMatchStrategy,
        fwDateColumn,
        sourceDateStart,
        sourceDateEnd,
        sourceDateFormat,
        targetDateStart,
        targetDateEnd,
        targetDateFormat,
        fwSourceSample,
        fwTargetSample,
        jsonConfigured: fileFormat === 'json' ? true : undefined,
      },
    }))
  }

  function loadUnitConfig(unitId) {
    const cfg = unitConfigs[unitId]
    if (!cfg) {
      setMappings([])
      setUidColumn('id')
      setColumnPreview({
        sourceColumns: [],
        targetColumns: [],
        compareColumns: [],
        autoMappings: [],
        unmatchedSourceColumns: [],
        unmatchedTargetColumns: [],
        delimiter: 'auto',
        sourceSamples: {},
        targetSamples: {},
        sampleRowCount: 6,
      })
      setFormatChecks([])
      setFooterValidation(null)
      setTestMode('full')
      setUidGte('')
      return
    }
    setMappings(cfg.mappings || [])
    setUidColumn(cfg.uidColumn || 'id')
    setDelimiter(cfg.delimiter || 'auto')
    setHasHeader(cfg.hasHeader !== false)
    setValidateHeaderFormats(cfg.validateHeaderFormats || false)
    setValidateFooters(cfg.validateFooters || false)
    setHeaderLeadingRows(cfg.headerLeadingRows || 0)
    setFooterTrailingRows(cfg.footerTrailingRows || 1)
    setTestMode(cfg.testMode || 'full')
    setUidGte(cfg.uidGte || '')
    setColumnPreview(cfg.columnPreview || {
      sourceColumns: [],
      targetColumns: [],
      compareColumns: [],
      autoMappings: [],
      unmatchedSourceColumns: [],
      unmatchedTargetColumns: [],
      delimiter: 'auto',
      sourceSamples: {},
      targetSamples: {},
      sampleRowCount: 6,
    })
    setFormatChecks(cfg.formatChecks || [])
    setFooterValidation(cfg.footerValidation ?? null)
    if (fileFormat === 'fixed-width') {
      setFwColumns(cfg.fwColumns || [])
      setFwJoinColumn(cfg.fwJoinColumn || 'name')
      setFwMatchStrategy(cfg.fwMatchStrategy || 'fuzzy')
      setFwDateColumn(cfg.fwDateColumn || 'dob')
      setSourceDateStart(cfg.sourceDateStart ?? 58)
      setSourceDateEnd(cfg.sourceDateEnd ?? 68)
      setSourceDateFormat(cfg.sourceDateFormat || 'dd/mm/yyyy')
      setTargetDateStart(cfg.targetDateStart ?? 58)
      setTargetDateEnd(cfg.targetDateEnd ?? 68)
      setTargetDateFormat(cfg.targetDateFormat || 'yyyy/mm/dd')
      setFwSourceSample(cfg.fwSourceSample || '')
      setFwTargetSample(cfg.fwTargetSample || '')
    }
  }

  function switchActiveUnit(unitId) {
    persistActiveUnitConfig()
    setActiveUnitId(unitId)
    loadUnitConfig(unitId)
  }

  const activeUnitIndex = mappingQueueUnits.findIndex(u => u.unitId === activeUnitId)
  const sequentialBatchMapping = multiPairBatch
    && (batchColumnMappingMode === 'manual' || batchColumnMappingMode === 'template-fixups')
  const showBatchMappingModeChoice = multiPairBatch && batchColumnMappingMode === 'choose'
  const showTemplateMapping = multiPairBatch && batchColumnMappingMode === 'template'

  function isCurrentPairMappingValid() {
    if (fileFormat === 'json') return true
    if (fileFormat === 'fixed-width') {
      return fwColumns.length > 0 && !!fwJoinColumn && !!sourceDateFormat.trim() && !!targetDateFormat.trim()
    }
    const hasMappedColumns = mappings.some(row => {
      const primary = String(row.targetCol || '').trim()
      if (primary) return true
      return Array.isArray(row.targetCols) && row.targetCols.some(col => String(col || '').trim())
    })
    if (testMode === 'litmus') return hasMappedColumns || columnPreview.compareColumns.length > 0
    return !!uidColumn.trim() && hasMappedColumns
  }

  function isUnitMappingConfigured(unitId) {
    if (fileFormat === 'json' && multiPairBatch) {
      if (unitId === activeUnitId && batchColumnMappingMode === 'manual') {
        return true
      }
      return Boolean(unitConfigs[unitId]?.jsonConfigured)
    }
    if (unitId === activeUnitId) return isCurrentPairMappingValid()
    const cfg = unitConfigs[unitId]
    if (!cfg) return false
    if (fileFormat === 'json') return true
    if (fileFormat === 'fixed-width') {
      return (cfg.fwColumns?.length ?? 0) > 0 && !!cfg.fwJoinColumn
    }
    const rows = Array.isArray(cfg.mappings) ? cfg.mappings : []
    const hasMappedColumns = rows.some(row => {
      const primary = String(row.targetCol || '').trim()
      if (primary) return true
      return Array.isArray(row.targetCols) && row.targetCols.some(col => String(col || '').trim())
    })
    if ((cfg.testMode || 'full') === 'litmus') {
      return hasMappedColumns || ((cfg.columnPreview?.compareColumns?.length ?? 0) > 0)
    }
    const uid = String(cfg.uidColumn || '').trim()
    return !!uid && hasMappedColumns
  }

  function goToPairAtIndex(index) {
    if (index < 0 || index >= mappingQueueUnits.length) return
    persistActiveUnitConfig()
    const unit = mappingQueueUnits[index]
    setActiveUnitId(unit.unitId)
    loadUnitConfig(unit.unitId)
  }

  function handleBatchMappingModeSelect(mode) {
    setBatchApplyAllError('')
    setBatchMismatchUnitIds([])
    setBatchMismatchDetails({})
    setUnitConfigs({})
    const firstId = validationUnits[0]?.unitId
    if (!firstId) return
    if (mode === 'manual') {
      setBatchColumnMappingMode('manual')
      setActiveUnitId(firstId)
      loadUnitConfig(firstId)
      return
    }
    if (mode === 'template') {
      setBatchColumnMappingMode('template')
      setActiveUnitId(firstId)
      loadUnitConfig(firstId)
    }
  }

  async function handleApplyTemplateToAll() {
    if (fileFormat !== 'json' && !isCurrentPairMappingValid()) return
    setBatchApplyAllLoading(true)
    setBatchApplyAllError('')
    try {
      const apiFileFormat = backendFileFormat(fileFormat)
      const template = fileFormat === 'fixed-width'
        ? buildFixedWidthTemplateSnapshot({
          fwColumns,
          fwJoinColumn,
          fwMatchStrategy,
          fwDateColumn,
          sourceDateStart,
          sourceDateEnd,
          sourceDateFormat,
          targetDateStart,
          targetDateEnd,
          targetDateFormat,
        })
        : fileFormat === 'json'
          ? buildJsonTemplateSnapshot()
          : buildCsvTemplateSnapshot({
            mappings,
            uidColumn,
            delimiter,
            hasHeader,
            validateHeaderFormats,
            validateFooters,
            headerLeadingRows,
            footerTrailingRows,
            testMode,
            uidGte,
            columnPreview,
          })
      const { unitConfigs: allConfigs, mismatchUnitIds, mismatchDetails } = await applyTemplateToAllUnits(
        validationUnits,
        template,
        {
          sourceStorageType,
          targetStorageType,
          sourceCloudConfig,
          targetCloudConfig,
        },
        apiFileFormat,
      )
      setUnitConfigs(allConfigs)
      if (mismatchUnitIds.length === 0) {
        setBatchColumnMappingMode('manual')
        setStep(4)
        return
      }
      setBatchMismatchUnitIds(mismatchUnitIds)
      setBatchMismatchDetails(mismatchDetails)
      setBatchColumnMappingMode('template-fixups')
      const firstMismatch = mismatchUnitIds[0]
      setActiveUnitId(firstMismatch)
      loadUnitConfig(firstMismatch)
    } catch (err) {
      setBatchApplyAllError(err instanceof Error ? err.message : String(err))
    } finally {
      setBatchApplyAllLoading(false)
    }
  }

  function handleConfigureContinue() {
    if ((sequentialBatchMapping || showTemplateMapping) && !isCurrentPairMappingValid()) return
    persistActiveUnitConfig()
    if (sequentialBatchMapping && activeUnitIndex >= 0 && activeUnitIndex < mappingQueueUnits.length - 1) {
      goToPairAtIndex(activeUnitIndex + 1)
      return
    }
    setStep(4)
  }

  function handleConfigureBack() {
    persistActiveUnitConfig()
    if (sequentialBatchMapping && activeUnitIndex > 0) {
      goToPairAtIndex(activeUnitIndex - 1)
      return
    }
    if (showTemplateMapping || batchColumnMappingMode === 'template-fixups') {
      setBatchColumnMappingMode('choose')
      setBatchMismatchUnitIds([])
      setBatchMismatchDetails({})
      return
    }
    if (inputLayout === 'pair') {
      setStep(1)
      setSubPhase('unified-selection')
    } else {
      setStep(2)
      setSubPhase(inputLayout === 'folder' ? 'file-pairing' : 'pick-target')
    }
  }

  function parseSelection(selection) {
    if (typeof selection === 'string') return { kind: 'file', path: selection }
    if (selection && typeof selection === 'object') return selection
    return null
  }

  async function runAutoPairing(sourceDir, targetDir) {
    setPairingLoading(true)
    setPairingError('')
    try {
      const data = await matchFilePairs({
        sourceDirectory: sourceDir,
        targetDirectory: targetDir,
        fileFormat: apiFileFormat,
        recursive: recursiveFolderMatch,
      })
      setPairingState({
        pairs: data.pairs || [],
        unmatchedSources: data.unmatched_sources || [],
        unmatchedTargets: data.unmatched_targets || [],
      })
      setSubPhase('file-pairing')
    } catch (err) {
      setPairingError(err instanceof Error ? err.message : String(err))
    } finally {
      setPairingLoading(false)
    }
  }

  async function runAutoPairingCloud(sourcePrefix, targetPrefix) {
    setPairingLoading(true)
    setPairingError('')
    try {
      const data = await matchCloudFilePairs({
        bucket: sourceCloudConfig.bucket,
        sourcePrefix,
        targetPrefix,
        credentialsJson: sourceCloudConfig.credentialsJson,
        connectionId: sourceCloudConfig.connectionId || undefined,
        projectId: sourceCloudConfig.projectId,
        fileFormat: apiFileFormat,
        recursive: recursiveFolderMatch,
      })
      setPairingState({
        pairs: data.pairs || [],
        unmatchedSources: data.unmatched_sources || [],
        unmatchedTargets: data.unmatched_targets || [],
      })
      setSubPhase('file-pairing')
    } catch (err) {
      setPairingError(err instanceof Error ? err.message : String(err))
    } finally {
      setPairingLoading(false)
    }
  }

  function applyCloudConfig(parsed) {
    setSourceCloudConfig({
      provider: 'google-cloud-storage',
      bucket: parsed.bucket || '',
      objectName: parsed.objectName || '',
      credentialsJson: parsed.credentialsJson || '',
      projectId: parsed.projectId || '',
    })
    setTargetCloudConfig({
      provider: 'google-cloud-storage',
      bucket: parsed.bucket || '',
      objectName: '',
      credentialsJson: parsed.credentialsJson || '',
      projectId: parsed.projectId || '',
    })
  }

  function applySavedCloudConnection(setter, connectionId) {
    const selected = savedCloudConnections.find((row) => String(row.id) === String(connectionId))
    if (!selected) {
      setter((prev) => ({ ...prev, connectionId: '', bucket: '', projectId: '', credentialsJson: '' }))
      return
    }
    setter((prev) => ({
      ...prev,
      connectionId: String(selected.id),
      provider: selected.provider || 'google-cloud-storage',
      bucket: selected.bucket || '',
      projectId: selected.project_id || '',
      credentialsJson: '',
    }))
  }

  function handleSourceSelected(selection) {
    const parsed = parseSelection(selection)
    if (!parsed) return
    if (parsed.kind === 'cloud') {
      setSourceCloudConfig(resolveCloudConfig({
        provider: parsed.provider || 'google-cloud-storage',
        bucket: parsed.bucket || '',
        objectName: parsed.objectName || '',
        credentialsJson: parsed.credentialsJson || '',
        projectId: parsed.projectId || '',
        connectionId: parsed.connectionId || sourceCloudConfig.connectionId || '',
      }, savedCloudConnections))
      setTargetCloudConfig(prev => resolveCloudConfig({
        ...prev,
        bucket: parsed.bucket || prev.bucket,
        credentialsJson: parsed.credentialsJson || prev.credentialsJson,
        connectionId: parsed.connectionId || prev.connectionId,
        projectId: parsed.projectId || prev.projectId,
      }, savedCloudConnections))
      setSourcePath('')
      setSubPhase(inputLayout === 'source-one-target-many' ? 'pick-target-multi' : 'pick-target')
      return
    }
    if (parsed.kind === 'cloud-folder') {
      applyCloudConfig(parsed)
      setSourceCloudPrefix(parsed.prefix || '')
      setSubPhase('pick-target-folder')
      return
    }
    if (parsed.kind === 'cloud-files') {
      applyCloudConfig(parsed)
      setSourceMultiPaths(parsed.objectNames || [])
      setSubPhase('pick-target')
      return
    }
    if (inputLayout === 'folder' && parsed.kind === 'folder') {
      setSourceFolder(parsed.path)
      setSubPhase('pick-target-folder')
      return
    }
    if (inputLayout === 'source-many-target-one' && parsed.kind === 'files') {
      setSourceMultiPaths(parsed.paths || [])
      setSubPhase('pick-target')
      return
    }
    if (parsed.kind === 'file' || typeof selection === 'string') {
      setSourcePath(parsed.path || selection)
    }
    if (inputLayout === 'source-one-target-many') setSubPhase('pick-target-multi')
    else setSubPhase('pick-target')
  }

  function handleTargetSelected(selection) {
    const parsed = parseSelection(selection)
    if (!parsed) return
    if (parsed.kind === 'cloud') {
      setTargetCloudConfig(resolveCloudConfig({
        provider: parsed.provider || 'google-cloud-storage',
        bucket: parsed.bucket || '',
        objectName: parsed.objectName || '',
        credentialsJson: parsed.credentialsJson || '',
        projectId: parsed.projectId || '',
        connectionId: parsed.connectionId || targetCloudConfig.connectionId || '',
      }, savedCloudConnections))
      setTargetPath('')
      if (inputLayout === 'source-many-target-one' && sourceMultiPaths.length) {
        const unit = unitFromMerge({
          sourcePaths: sourceMultiPaths,
          targetPaths: [parsed.objectName],
          label: `${sourceMultiPaths.length} sources → ${parsed.objectName}`,
        })
        setValidationUnits([unit])
        setActiveUnitId(unit.unitId)
      }
      setStep(3)
      return
    }
    if (parsed.kind === 'cloud-folder') {
      applyCloudConfig(parsed)
      setTargetCloudPrefix(parsed.prefix || '')
      runAutoPairingCloud(sourceCloudPrefix, parsed.prefix || '')
      return
    }
    if (inputLayout === 'source-one-target-many' && parsed.kind === 'cloud-files') {
      applyCloudConfig(parsed)
      const srcObject = sourceCloudConfig.objectName?.trim()
      if (!srcObject) {
        setPairingError('Select a single source object first')
        return
      }
      const unit = unitFromMerge({
        sourcePaths: [srcObject],
        targetPaths: parsed.objectNames || [],
        label: `${srcObject.split('/').pop()} → ${(parsed.objectNames || []).length} targets`,
      })
      setValidationUnits([unit])
      setActiveUnitId(unit.unitId)
      setStep(3)
      return
    }
    if (inputLayout === 'folder' && parsed.kind === 'folder') {
      setTargetFolder(parsed.path)
      runAutoPairing(sourceFolder, parsed.path)
      return
    }
    if (inputLayout === 'source-one-target-many' && parsed.kind === 'files') {
      const unit = unitFromMerge({
        sourcePaths: [sourcePath],
        targetPaths: parsed.paths || [],
        label: `${sourcePath.split('/').pop()} → ${parsed.paths.length} targets`,
      })
      setValidationUnits([unit])
      setActiveUnitId(unit.unitId)
      setStep(3)
      return
    }
    if (inputLayout === 'source-many-target-one' && (parsed.kind === 'file' || typeof selection === 'string')) {
      const target = parsed.path || selection
      setTargetPath(target)
      const unit = unitFromMerge({
        sourcePaths: sourceMultiPaths,
        targetPaths: [target],
        label: `${sourceMultiPaths.length} sources → ${target.split('/').pop()}`,
      })
      setValidationUnits([unit])
      setActiveUnitId(unit.unitId)
      setStep(3)
      return
    }
    if (parsed.kind === 'file' || typeof selection === 'string') {
      setTargetPath(parsed.path || selection)
    }
    setStep(3)
  }

  function handlePairingComplete(pairs) {
    const units = unitsFromPairs(pairs)
    setValidationUnits(units)
    setUnitConfigs({})
    setBatchColumnMappingMode(
      units.length > 1 && (isCsvLikeFormat(fileFormat) || fileFormat === 'fixed-width' || fileFormat === 'json')
        ? 'choose'
        : 'manual',
    )
    setBatchMismatchUnitIds([])
    setBatchMismatchDetails({})
    setBatchApplyAllError('')
    if (units.length === 1) {
      setActiveUnitId(units[0]?.unitId || null)
      if (units[0]?.unitId) loadUnitConfig(units[0].unitId)
    } else {
      setActiveUnitId(null)
    }
    setStep(3)
  }

  useEffect(() => {
    const hasSource = isBatchMode
      ? Boolean(activeUnit?.sourcePaths?.length)
      : isStorageSelectionComplete(sourceStorageType, sourcePath, sourceCloudConfig)
    const hasTarget = isBatchMode
      ? Boolean(activeUnit?.targetPaths?.length)
      : isStorageSelectionComplete(targetStorageType, targetPath, targetCloudConfig)
    if (step !== 3 || showBatchMappingModeChoice || !hasSource || !hasTarget || fileFormat === 'fixed-width' || fileFormat === 'json') return

    const controller = new AbortController()

    async function loadColumnPreview() {
      setColumnPreviewLoading(true)
      setColumnPreviewError('')
      try {
        const previewSourcePath = isBatchMode ? effectiveSourcePath : sourcePath
        const previewTargetPath = isBatchMode ? effectiveTargetPath : targetPath
        const previewSourceCloudConfig = sourceStorageType === 'cloud'
          ? {
              ...sourceCloudConfig,
              objectName: (isBatchMode && activeUnit?.sourcePaths?.[0]) || sourceCloudConfig.objectName,
            }
          : sourceCloudConfig
        const previewTargetCloudConfig = targetStorageType === 'cloud'
          ? {
              ...targetCloudConfig,
              objectName: (isBatchMode && activeUnit?.targetPaths?.[0]) || targetCloudConfig.objectName,
            }
          : targetCloudConfig
        const res = await fetch(absoluteApiUrl('/api/v1/validate/local/columns'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify(
            {
              ...buildStoragePayload('source', sourceStorageType, previewSourcePath, previewSourceCloudConfig, savedCloudConnections),
              ...buildStoragePayload('target', targetStorageType, previewTargetPath, previewTargetCloudConfig, savedCloudConnections),
              uid_column: uidColumn.trim(),
              delimiter: delimiter.trim() || 'auto',
              has_header: hasHeader,
              header_leading_rows: headerLeadingRows,
            },
          ),
        })
        const raw = await res.text()
        let data = {}
        if (raw) {
          try { data = JSON.parse(raw) } catch { throw new Error(raw.trim().slice(0, 500)) }
        }
        if (!res.ok) throw new Error(formatDetail(data.detail) || `${res.status} ${res.statusText}`)

        if (typeof data.inferred_has_header === 'boolean' && data.inferred_has_header !== hasHeader) {
          setHasHeader(data.inferred_has_header)
          return
        }

        const sourceColumns = Array.isArray(data.source_columns) ? data.source_columns : []
        const targetColumns = Array.isArray(data.target_columns) ? data.target_columns : []
        const compareColumns = Array.isArray(data.compare_columns) ? data.compare_columns : sourceColumns.filter(col => col !== uidColumn.trim())
        const autoMappings = Array.isArray(data.auto_mappings) ? data.auto_mappings : []
        setColumnPreview({
          sourceColumns,
          targetColumns,
          compareColumns,
          autoMappings,
          unmatchedSourceColumns: Array.isArray(data.unmatched_source_columns) ? data.unmatched_source_columns : [],
          unmatchedTargetColumns: Array.isArray(data.unmatched_target_columns) ? data.unmatched_target_columns : [],
          delimiter: data.delimiter || delimiter,
          sourceSamples: data.source_samples && typeof data.source_samples === 'object' ? data.source_samples : {},
          targetSamples: data.target_samples && typeof data.target_samples === 'object' ? data.target_samples : {},
          sampleRowCount: Number(data.sample_row_count) || 6,
        })
        let effectiveUid = uidColumn.trim()
        if (!effectiveUid || !sourceColumns.includes(effectiveUid)) {
          effectiveUid = pickDefaultUidColumn(sourceColumns, hasHeader)
          if (effectiveUid) setUidColumn(effectiveUid)
        }
        setMappings(prev => buildMappingRows(
          compareColumns,
          targetColumns.filter(col => col !== effectiveUid),
          prev,
          autoMappings,
        ))
      } catch (err) {
        if (err?.name !== 'AbortError') {
          setColumnPreviewError(err instanceof Error ? err.message : String(err))
          setColumnPreview({
            sourceColumns: [],
            targetColumns: [],
            compareColumns: [],
            autoMappings: [],
            unmatchedSourceColumns: [],
            unmatchedTargetColumns: [],
            delimiter,
            sourceSamples: {},
            targetSamples: {},
            sampleRowCount: 6,
          })
          setMappings([])
        }
      } finally {
        if (!controller.signal.aborted) setColumnPreviewLoading(false)
      }
    }

    loadColumnPreview()
    return () => controller.abort()
  }, [
    step,
    isBatchMode,
    activeUnitId,
    effectiveSourcePath,
    effectiveTargetPath,
    sourceStorageType,
    targetStorageType,
    sourcePath,
    targetPath,
    sourceCloudConfig,
    targetCloudConfig,
    uidColumn,
    delimiter,
    hasHeader,
    headerLeadingRows,
    fileFormat,
    showBatchMappingModeChoice,
  ])

  useEffect(() => {
    const fwSource = isBatchMode ? (effectiveSourcePath || '').trim() : sourcePath.trim()
    const fwTarget = isBatchMode ? (effectiveTargetPath || '').trim() : targetPath.trim()
    const hasSource = isBatchMode ? Boolean(fwSource) : isStorageSelectionComplete(sourceStorageType, sourcePath, sourceCloudConfig)
    const hasTarget = isBatchMode ? Boolean(fwTarget) : isStorageSelectionComplete(targetStorageType, targetPath, targetCloudConfig)
    if ((step !== 3 && step !== 4) || showBatchMappingModeChoice || !hasSource || !hasTarget || fileFormat !== 'fixed-width') return
    if (isBatchMode && activeUnitId && (unitConfigs[activeUnitId]?.fwColumns?.length ?? 0) > 0) return

    const controller = new AbortController()
    const params = new URLSearchParams()
    if (fwSource) params.set('source_path', fwSource)
    if (fwTarget) params.set('target_path', fwTarget)
    if (!params.get('source_path') || !params.get('target_path')) return

    async function loadLayout() {
      setFwLayoutLoading(true)
      setFwLayoutError('')
      try {
        const res = await fetch(
          absoluteApiUrl(`/api/v1/validate/local/fixed-width/columns?${params}`),
          { signal: controller.signal },
        )
        const raw = await res.text()
        let data = {}
        if (raw) try { data = JSON.parse(raw) } catch { throw new Error(raw.trim().slice(0, 400)) }
        if (!res.ok) throw new Error(formatDetail(data.detail) || `${res.status} ${res.statusText}`)
        const cols = Array.isArray(data.columns) ? data.columns : []
        setFwColumns(cols)
        setFwSourceSample(data.source_sample || '')
        setFwTargetSample(data.target_sample || '')
        const suggested = data.suggested_join_column || cols[0]?.field_name || 'id'
        setFwJoinColumn(suggested)
        const dateName = cols.some(c => c.field_name === 'dob') ? 'dob' : (cols[cols.length - 1]?.field_name || 'dob')
        setFwDateColumn(dateName)
        const dcol = cols.find(c => c.field_name === dateName)
        if (dcol && !preserveFixedWidthDatesRef.current) {
          setSourceDateStart(Number(dcol.source_start))
          setSourceDateEnd(Number(dcol.source_end))
          setTargetDateStart(Number(dcol.target_start))
          setTargetDateEnd(Number(dcol.target_end))
        }
        preserveFixedWidthDatesRef.current = false
      } catch (err) {
        if (err?.name !== 'AbortError') {
          setFwLayoutError(err instanceof Error ? err.message : String(err))
          setFwColumns([])
        }
      } finally {
        if (!controller.signal.aborted) setFwLayoutLoading(false)
      }
    }
    loadLayout()
    return () => controller.abort()
  }, [
    step,
    sourceStorageType,
    targetStorageType,
    sourcePath,
    targetPath,
    fileFormat,
    isBatchMode,
    effectiveSourcePath,
    effectiveTargetPath,
    activeUnitId,
    unitConfigs,
    showBatchMappingModeChoice,
  ])

  useEffect(() => {
    const hasSource = isStorageSelectionComplete(sourceStorageType, sourcePath, sourceCloudConfig)
    const hasTarget = isStorageSelectionComplete(targetStorageType, targetPath, targetCloudConfig)
    if (step !== 3 || !hasSource || !hasTarget || fileFormat === 'fixed-width' || fileFormat === 'json') return
    if (!validateHeaderFormats && !validateFooters) {
      setFormatChecks([])
      setFooterValidation(null)
      setAnalyzeError('')
      return
    }

    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setAnalyzeLoading(true)
      setAnalyzeError('')
      try {
        const res = await fetch(absoluteApiUrl('/api/v1/validate/local/analyze'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify(buildAnalyzePayload({
            sourceStorageType,
            sourcePath,
            sourceCloudConfig,
            targetStorageType,
            targetPath,
            targetCloudConfig,
            uidColumn,
            delimiter,
            mappings,
            validateHeaderFormats,
            validateFooters,
            headerLeadingRows,
            footerTrailingRows,
            hasHeader,
          })),
        })
        const raw = await res.text()
        let data = {}
        if (raw) {
          try { data = JSON.parse(raw) } catch { throw new Error(raw.trim().slice(0, 500)) }
        }
        if (!res.ok) throw new Error(formatDetail(data.detail) || `${res.status} ${res.statusText}`)
        setFormatChecks(Array.isArray(data.format_checks) ? data.format_checks : [])
        setFooterValidation(data.footer_validation ?? null)
      } catch (err) {
        if (err?.name !== 'AbortError') {
          setAnalyzeError(err instanceof Error ? err.message : String(err))
          setFormatChecks([])
          setFooterValidation(null)
        }
      } finally {
        if (!controller.signal.aborted) setAnalyzeLoading(false)
      }
    }, 400)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [
    step,
    sourcePath,
    targetPath,
    sourceStorageType,
    targetStorageType,
    sourceCloudConfig,
    targetCloudConfig,
    uidColumn,
    delimiter,
    mappings,
    validateHeaderFormats,
    validateFooters,
    headerLeadingRows,
    footerTrailingRows,
    hasHeader,
    fileFormat,
  ])

  async function handleValidate() {
    setIsRunning(true); setPhase('running'); setResult(null); setBatchResult(null); setErrorMsg('')
    try {
      const apiFileFormat = backendFileFormat(fileFormat)
      if (isBatchMode) {
        persistActiveUnitConfig()
        const mergedConfigs = {
          ...unitConfigs,
          ...(activeUnitId ? {
            [activeUnitId]: {
              ...(unitConfigs[activeUnitId] || {}),
              mappings,
              uidColumn,
              delimiter,
              hasHeader,
              validateHeaderFormats,
              validateFooters,
              headerLeadingRows,
              footerTrailingRows,
              testMode,
              uidGte,
              columnMappings: toColumnMappingPayload(mappings),
            },
          } : {}),
        }
        const bodyPayload = buildBatchValidatePayload({
          fileFormat: apiFileFormat,
          units: validationUnits,
          unitConfigs: Object.fromEntries(
            validationUnits.map(u => [u.unitId, {
              ...(mergedConfigs[u.unitId] || {}),
              columnMappings: toColumnMappingPayload(mergedConfigs[u.unitId]?.mappings || mappings),
              uidColumn: mergedConfigs[u.unitId]?.uidColumn || uidColumn,
            }]),
          ),
          onUnitFailure,
          delimiter,
          hasHeader,
          headerLeadingRows,
          validateHeaderFormats,
          validateFooters,
          footerTrailingRows,
          testMode,
          uidGte,
          fixedWidthConfigBuilder: cfg => buildFixedWidthValidateConfig({
            columns: cfg.fwColumns || fwColumns,
            joinColumn: cfg.fwJoinColumn || fwJoinColumn,
            matchStrategy: cfg.fwMatchStrategy || fwMatchStrategy,
            dateColumn: cfg.fwDateColumn || fwDateColumn,
            sourceDateStart: cfg.sourceDateStart ?? sourceDateStart,
            sourceDateEnd: cfg.sourceDateEnd ?? sourceDateEnd,
            sourceDateFormat: cfg.sourceDateFormat || sourceDateFormat,
            targetDateStart: cfg.targetDateStart ?? targetDateStart,
            targetDateEnd: cfg.targetDateEnd ?? targetDateEnd,
            targetDateFormat: cfg.targetDateFormat || targetDateFormat,
          }),
          cloudBucket: sourceStorageType === 'cloud' ? sourceCloudConfig.bucket : undefined,
          cloudCredentialsJson: sourceStorageType === 'cloud' ? sourceCloudConfig.credentialsJson : undefined,
          cloudProjectId: sourceStorageType === 'cloud' ? sourceCloudConfig.projectId : undefined,
        })
        const res = await fetch(absoluteApiUrl('/api/v1/validate/local/batch'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(bodyPayload),
        })
        const raw = await res.text()
        let data = {}
        if (raw) { try { data = JSON.parse(raw) } catch { data = { detail: raw.trim().slice(0, 800) } } }
        if (!res.ok) throw new Error(formatDetail(data.detail) || `${res.status} ${res.statusText}`)
        if (res.status === 202 && data.poll_url) {
          const jid = data.job_id != null ? String(data.job_id) : null
          setJobProgress({ phase: 'accepted', jobId: jid })
          const pollPayload = await pollJobDetail(data.poll_url, {
            timeoutMs: pollTimeoutMs,
            onPoll: payload => {
              const st = payload?.status
              setJobProgress(prev => ({ ...prev, phase: payload?.phase || (st === 'running' ? 'running' : st) || 'running' }))
            },
          })
          const batch = normalizeBatchPollResult(pollPayload)
          if (batch) {
            setBatchResult(batch)
            setPhase(batch.summary?.is_match ? 'success' : 'error')
            if (!batch.summary?.is_match) {
              setErrorMsg(`${batch.summary.failed_units} failed, ${batch.summary.total_units - batch.summary.passed_units} with mismatches`)
            }
          } else {
            throw new Error('Batch job completed without batch_result payload')
          }
        } else {
          throw new Error('Unexpected batch API response')
        }
        return
      }

      const sourcePayload = buildStoragePayload('source', sourceStorageType, sourcePath, sourceCloudConfig, savedCloudConnections)
      const targetPayload = buildStoragePayload('target', targetStorageType, targetPath, targetCloudConfig, savedCloudConnections)
      const bodyPayload = fileFormat === 'fixed-width' ? {
        ...sourcePayload,
        ...targetPayload,
        file_format: 'fixed-width',
        delimiter: 'fixed',
        fixed_width_config: buildFixedWidthValidateConfig({
          columns: fwColumns,
          joinColumn: fwJoinColumn,
          matchStrategy: fwMatchStrategy,
          dateColumn: fwDateColumn,
          sourceDateStart,
          sourceDateEnd,
          sourceDateFormat,
          targetDateStart,
          targetDateEnd,
          targetDateFormat,
        }),
      } : fileFormat === 'json' ? {
        ...sourcePayload,
        ...targetPayload,
        file_format: 'json',
        delimiter: 'json',
        uid_column: 'document',
      } : {
        ...sourcePayload,
        ...targetPayload,
        uid_column: uidColumn.trim(),
        delimiter: delimiter.trim() || 'auto',
        column_mappings: toColumnMappingPayload(mappings),
        validate_header_formats: validateHeaderFormats,
        validate_footers: validateFooters,
        header_leading_rows: headerLeadingRows,
        footer_trailing_rows: footerTrailingRows,
        test_mode: testMode,
        uid_gte: uidGte.trim() || undefined,
        has_header: hasHeader,
        file_format: apiFileFormat
      };

      const res = await fetch(absoluteApiUrl('/api/v1/validate/local'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyPayload),
      })
      const raw = await res.text()
      let data = {}
      if (raw) { try { data = JSON.parse(raw) } catch { data = { detail: raw.trim().slice(0, 800) } } }
      if (!res.ok) throw new Error(formatDetail(data.detail) || `${res.status} ${res.statusText}`)
      let final = data
      if (res.status === 202 && data.poll_url) {
        const jid = data.job_id != null ? String(data.job_id) : null
        setJobProgress({ phase: 'accepted', jobId: jid })
        final = await pollJob(data.poll_url, {
          timeoutMs: pollTimeoutMs,
          onPoll: payload => {
            const st = payload?.status
            setJobProgress(prev => ({ ...prev, phase: payload?.phase || (st === 'running' ? 'running' : st) || 'running' }))
          },
        })
      } else if (data.summary) {
        final = normalizeResult(data)
      } else {
        throw new Error('Unexpected API response')
      }
      setResult(final); setPhase('success')
    } catch (err) {
      setPhase('error')
      setErrorMsg(formatJobError(err instanceof Error ? err.message : String(err)))
    } finally { setIsRunning(false) }
  }

  async function handleSaveAsDraft() {
    setDraftSaveStatus('saving')
    setDraftSaveError('')
    try {
      const sourceDisplay = describeStorageInput(sourceStorageType, sourcePath, sourceCloudConfig)
      const targetDisplay = describeStorageInput(targetStorageType, targetPath, targetCloudConfig)
      const draftPayload = fileFormat === 'fixed-width' ? {
        sourcePath: sourceDisplay,
        targetPath: targetDisplay,
        uidColumn: 'date',
        delimiter: 'fixed',
        columnMappings: [
          { source_column: 'source_date_start', target_column: String(sourceDateStart) },
          { source_column: 'source_date_end', target_column: String(sourceDateEnd) },
          { source_column: 'source_date_format', target_column: sourceDateFormat.trim() },
          { source_column: 'target_date_start', target_column: String(targetDateStart) },
          { source_column: 'target_date_end', target_column: String(targetDateEnd) },
          { source_column: 'target_date_format', target_column: targetDateFormat.trim() },
        ],
        validateHeaderFormats: false,
        validateFooters: false,
      } : {
        sourcePath: sourceDisplay,
        targetPath: targetDisplay,
        uidColumn: uidColumn.trim(),
        delimiter: delimiter.trim() || 'auto',
        columnMappings: toColumnMappingPayload(mappings),
        validateHeaderFormats,
        validateFooters,
        headerLeadingRows,
        footerTrailingRows,
        testMode,
        uidGte,
      };

      await saveValidationDraft(draftPayload)
      setDraftSaveStatus('success')
      setTimeout(() => {
        setDraftSaveStatus(prev => prev === 'success' ? 'idle' : prev)
      }, 6000)
    } catch (err) {
      setDraftSaveStatus('error')
      setDraftSaveError(err instanceof Error ? err.message : String(err))
    }
  }


  const showUnifiedSelection = step === 1 && subPhase === 'unified-selection'
  const showFormatSelect = step === 1 && subPhase === 'format-select'
  const showInputLayout = step === 2 && subPhase === 'input-layout'
  const showTypeSelect = step === 2 && subPhase === 'type-select'
  const showPickSource = step === 2 && (subPhase === 'pick-source' || subPhase === 'pick-source-folder' || subPhase === 'pick-source-multi')
  const showPickTarget = step === 2 && (subPhase === 'pick-target' || subPhase === 'pick-target-folder' || subPhase === 'pick-target-multi')
  const showFilePairing = step === 2 && subPhase === 'file-pairing'
  const showConfigure  = step === 3
  const showReview     = step === 4
  const allBatchUnitsConfigured = multiPairBatch
    ? validationUnits.every(u => isUnitMappingConfigured(u.unitId))
    : true

  const isValidForRun  = isBatchMode
    ? validationUnits.length > 0 && allBatchUnitsConfigured && (fileFormat === 'json'
      ? true
      : fileFormat === 'fixed-width'
        ? fwColumns.length > 0 && !!fwJoinColumn
        : isCurrentPairMappingValid())
    : fileFormat === 'json'
    ? (isStorageSelectionComplete(sourceStorageType, sourcePath, sourceCloudConfig)
      && isStorageSelectionComplete(targetStorageType, targetPath, targetCloudConfig))
    : fileFormat === 'fixed-width'
    ? (isStorageSelectionComplete(sourceStorageType, sourcePath, sourceCloudConfig)
      && isStorageSelectionComplete(targetStorageType, targetPath, targetCloudConfig)
      && fwColumns.length > 0
      && !!fwJoinColumn
      && !!sourceDateFormat.trim()
      && !!targetDateFormat.trim())
    : (isStorageSelectionComplete(sourceStorageType, sourcePath, sourceCloudConfig)
      && isStorageSelectionComplete(targetStorageType, targetPath, targetCloudConfig)
      && isCurrentPairMappingValid())
  const sourceDisplay = isBatchMode && activeUnit
    ? activeUnit.sourcePaths.join(', ')
    : describeStorageInput(sourceStorageType, sourcePath, sourceCloudConfig)
  const targetDisplay = isBatchMode && activeUnit
    ? activeUnit.targetPaths.join(', ')
    : describeStorageInput(targetStorageType, targetPath, targetCloudConfig)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* Premium Draft Notification Banners */}
      {draftSaveStatus === 'saving' && (
        <div style={{
          padding: '14px 18px',
          background: 'var(--surface-1)',
          color: 'var(--text-2)',
          border: '1px solid var(--border-1)',
          borderRadius: 12,
          fontSize: 13,
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}>
          <span style={{
            display: 'inline-block',
            width: 12,
            height: 12,
            borderRadius: '50%',
            border: '2px solid rgba(0,0,0,0.1)',
            borderTopColor: 'var(--text-2)',
            animation: 'spin 0.7s linear infinite',
            marginRight: 4
          }} />
          Saving mapping configuration as draft…
        </div>
      )}

      {draftSaveStatus === 'success' && (
        <div style={{
          padding: '14px 18px',
          background: 'var(--success-0)',
          color: 'var(--success-2)',
          border: '1px solid var(--success-1)',
          borderRadius: 12,
          fontSize: 13,
          fontWeight: 500,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          animation: 'fadeIn 0.2s ease'
        }}>
          <span>✓ Mapping draft successfully saved to history! You can resume from the History tab at any time.</span>
          <button
            onClick={() => setDraftSaveStatus('idle')}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold', fontSize: 14 }}
          >
            ✕
          </button>
        </div>
      )}

      {draftSaveStatus === 'error' && (
        <div style={{
          padding: '14px 18px',
          background: 'var(--error-0)',
          color: 'var(--error-2)',
          border: '1px solid var(--error-1)',
          borderRadius: 12,
          fontSize: 13,
          fontWeight: 500,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          animation: 'fadeIn 0.2s ease'
        }}>
          <span>✗ Failed to save draft: {draftSaveError}</span>
          <button
            onClick={() => setDraftSaveStatus('idle')}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold', fontSize: 14 }}
          >
            ✕
          </button>
        </div>
      )}

      {columnPreviewError && (
        <div style={{
          padding: '14px 18px',
          background: 'var(--error-0)',
          color: 'var(--error-2)',
          border: '1px solid var(--error-1)',
          borderRadius: 12,
          fontSize: 13,
          fontWeight: 500,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          animation: 'fadeIn 0.2s ease',
          marginBottom: 8
        }}>
          <span>✗ {columnPreviewError}</span>
          <button
            onClick={() => setColumnPreviewError('')}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold', fontSize: 14 }}
          >
            ✕
          </button>
        </div>
      )}



      {/* Step indicator */}
      <div style={{
        background: 'var(--surface-1)', border: '1px solid var(--border-1)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        <StepIndicator currentStep={step} inputLayout={inputLayout} />
      </div>

      {/* Step content */}
      <div style={{
        background: 'var(--surface-1)', border: '1px solid var(--border-1)',
        borderRadius: 12, padding: '24px 28px',
      }}>

        {/* Step 1: Select Files & Layout */}
        {showUnifiedSelection && (
          <div style={{ animation: 'fade-in 0.2s ease' }}>
            {/* Page Header */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
                Step 1 of 3
              </div>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 6 }}>
                Select Files & Validation Layout
              </h2>
              <p style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.5 }}>
                Expose your source and target paths directly, and select a validation mode to run.
              </p>
            </div>

            {/* Validation Mode selector dropdown */}
            <div style={{
              background: 'var(--surface-2)',
              border: '1px solid var(--border-1)',
              borderRadius: 12,
              padding: '16px 20px',
              marginBottom: 24,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16,
              flexWrap: 'wrap',
            }}>
              <div>
                <h4 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)', margin: '0 0 4px 0' }}>
                  Validation Mode
                </h4>
                <p style={{ fontSize: 12, color: 'var(--text-3)', margin: 0 }}>
                  Define the file relationship layout for validation checks.
                </p>
              </div>
              <select
                value={inputLayout}
                onChange={e => {
                  setInputLayout(e.target.value)
                  // Clean paths when layout changes
                  setSourcePath('')
                  setTargetPath('')
                  setSourceMultiPaths([])
                  setTargetMultiPaths([])
                  setSourceFolder('')
                  setTargetFolder('')
                  setValidationUnits([])
                }}
                style={{
                  minWidth: 260,
                  height: 38,
                  borderRadius: 8,
                  border: '1px solid var(--border-2)',
                  background: 'var(--surface-1)',
                  color: 'var(--text-1)',
                  padding: '0 12px',
                  fontSize: 13,
                  fontWeight: 600,
                  outline: 'none',
                  cursor: 'pointer',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                }}
              >
                <option value="pair">Single file pair (Single-to-Single) [Primary]</option>
                <option value="folder">Folder ↔ folder</option>
                <option value="source-one-target-many">One source → many targets</option>
                <option value="source-many-target-one">Many sources → one target</option>
              </select>
            </div>

            {/* Two Column Layout for Source and Target */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 28 }}>
              {/* SOURCE COLUMN */}
              <div style={{
                background: 'var(--surface-1)',
                border: '1px solid var(--border-1)',
                borderRadius: 12,
                padding: 20,
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
                boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-1)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)' }}></span>
                    Source Location
                  </h3>
                  {/* Storage Segment Toggle */}
                  <div style={{
                    display: 'inline-flex',
                    background: 'var(--surface-3)',
                    borderRadius: 8,
                    padding: 2,
                    border: '1px solid var(--border-2)',
                  }}>
                    <button
                      type="button"
                      onClick={() => setSourceStorageType('local')}
                      style={{
                        padding: '4px 10px',
                        fontSize: 11,
                        fontWeight: 600,
                        borderRadius: 6,
                        border: 'none',
                        background: sourceStorageType === 'local' ? 'var(--surface-1)' : 'transparent',
                        color: sourceStorageType === 'local' ? 'var(--text-1)' : 'var(--text-3)',
                        cursor: 'pointer',
                        boxShadow: sourceStorageType === 'local' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                        transition: 'all 0.1s',
                      }}
                    >
                      Local Device
                    </button>
                    <button
                      type="button"
                      onClick={() => setSourceStorageType('cloud')}
                      style={{
                        padding: '4px 10px',
                        fontSize: 11,
                        fontWeight: 600,
                        borderRadius: 6,
                        border: 'none',
                        background: sourceStorageType === 'cloud' ? 'var(--surface-1)' : 'transparent',
                        color: sourceStorageType === 'cloud' ? 'var(--text-1)' : 'var(--text-3)',
                        cursor: 'pointer',
                        boxShadow: sourceStorageType === 'cloud' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                        transition: 'all 0.1s',
                      }}
                    >
                      Cloud Storage
                    </button>
                  </div>
                </div>

                {sourceStorageType === 'local' ? (
                  <div>
                    <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 6 }}>
                      {inputLayout === 'folder' ? 'Local Folder Path' : 'Local File Path'}
                    </label>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input
                        type="text"
                        value={
                          inputLayout === 'folder'
                            ? sourceFolder
                            : inputLayout === 'source-many-target-one'
                              ? sourceMultiPaths.join(', ')
                              : sourcePath
                        }
                        onChange={e => {
                          if (inputLayout === 'folder') setSourceFolder(e.target.value)
                          else if (inputLayout === 'source-many-target-one') setSourceMultiPaths(e.target.value.split(',').map(s => s.trim()).filter(Boolean))
                          else {
                            setSourcePath(e.target.value)
                            const detected = detectFormatFromPath(e.target.value)
                            if (detected) {
                              setFileFormat(detected)
                              setIsManualFormat(false)
                            }
                          }
                        }}
                        placeholder={inputLayout === 'folder' ? 'e.g. /path/to/source_folder' : 'e.g. /path/to/source_file.csv'}
                        style={{
                          flex: 1,
                          height: 38,
                          borderRadius: 8,
                          border: '1px solid var(--border-2)',
                          background: 'var(--surface-2)',
                          color: 'var(--text-1)',
                          padding: '0 12px',
                          fontSize: 13,
                          outline: 'none',
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => {
                          setBrowserTarget('source')
                          setIsBrowserOpen(true)
                        }}
                        className="btn btn-secondary"
                        style={{ height: 38, padding: '0 14px', fontSize: 13, fontWeight: 600 }}
                      >
                        Browse...
                      </button>
                    </div>
                    {inputLayout === 'source-many-target-one' && sourceMultiPaths.length > 0 && (
                      <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>
                        Selected {sourceMultiPaths.length} source file(s)
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 4 }}>
                        Saved Connection (Optional)
                      </label>
                      <select
                        value={sourceCloudConfig.connectionId || ''}
                        onChange={e => applySavedCloudConnection(setSourceCloudConfig, e.target.value)}
                        style={{
                          width: '100%',
                          height: 36,
                          borderRadius: 8,
                          border: '1px solid var(--border-2)',
                          background: 'var(--surface-2)',
                          color: 'var(--text-1)',
                          padding: '0 12px',
                          fontSize: 13,
                          outline: 'none',
                        }}
                      >
                        <option value="">-- Manual (paste JSON) --</option>
                        {savedCloudConnections.map((conn) => (
                          <option key={conn.id} value={conn.id}>
                            {conn.name} ({conn.bucket})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 4 }}>
                        Bucket Name
                      </label>
                      <input
                        type="text"
                        value={sourceCloudConfig.bucket}
                        onChange={e => setSourceCloudConfig(prev => resolveCloudConfig({ ...prev, bucket: e.target.value }, savedCloudConnections))}
                        placeholder="my-gcs-bucket"
                        style={{
                          width: '100%',
                          height: 36,
                          borderRadius: 8,
                          border: '1px solid var(--border-2)',
                          background: 'var(--surface-2)',
                          color: 'var(--text-1)',
                          padding: '0 12px',
                          fontSize: 13,
                          outline: 'none',
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 4 }}>
                        Project ID (Optional)
                      </label>
                      <input
                        type="text"
                        value={sourceCloudConfig.projectId}
                        onChange={e => setSourceCloudConfig(prev => ({ ...prev, projectId: e.target.value }))}
                        placeholder="my-gcs-project-id"
                        style={{
                          width: '100%',
                          height: 36,
                          borderRadius: 8,
                          border: '1px solid var(--border-2)',
                          background: 'var(--surface-2)',
                          color: 'var(--text-1)',
                          padding: '0 12px',
                          fontSize: 13,
                          outline: 'none',
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 4 }}>
                        Credentials JSON (Optional)
                      </label>
                      <textarea
                        value={sourceCloudConfig.credentialsJson}
                        disabled={Boolean(sourceCloudConfig.connectionId)}
                        onChange={e => setSourceCloudConfig(prev => ({ ...prev, connectionId: '', credentialsJson: e.target.value }))}
                        placeholder='{"type": "service_account", ...}'
                        style={{
                          width: '100%',
                          height: 50,
                          borderRadius: 8,
                          border: '1px solid var(--border-2)',
                          background: 'var(--surface-2)',
                          color: 'var(--text-1)',
                          padding: '8px 12px',
                          fontSize: 12,
                          outline: 'none',
                          resize: 'vertical',
                          opacity: sourceCloudConfig.connectionId ? 0.6 : 1,
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 4 }}>
                        {inputLayout === 'folder' ? 'Cloud Prefix (Folder)' : 'Object Name / Prefix'}
                      </label>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <input
                          type="text"
                          value={
                            inputLayout === 'folder'
                              ? sourceCloudPrefix
                              : inputLayout === 'source-many-target-one'
                                ? sourceMultiPaths.join(', ')
                                : sourceCloudConfig.objectName
                          }
                          onChange={e => {
                            if (inputLayout === 'folder') setSourceCloudPrefix(e.target.value)
                            else if (inputLayout === 'source-many-target-one') setSourceMultiPaths(e.target.value.split(',').map(s => s.trim()).filter(Boolean))
                            else setSourceCloudConfig(prev => ({
                              ...prev,
                              objectName: normalizeGcsObjectName(prev.bucket, e.target.value),
                            }))
                          }}
                          placeholder="e.g. data/sources/"
                          style={{
                            flex: 1,
                            height: 38,
                            borderRadius: 8,
                            border: '1px solid var(--border-2)',
                            background: 'var(--surface-2)',
                            color: 'var(--text-1)',
                            padding: '0 12px',
                            fontSize: 13,
                            outline: 'none',
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            setBrowserTarget('source')
                            setIsBrowserOpen(true)
                          }}
                          className="btn btn-secondary"
                          style={{ height: 38, padding: '0 14px', fontSize: 13, fontWeight: 600 }}
                        >
                          Browse...
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* TARGET COLUMN */}
              <div style={{
                background: 'var(--surface-1)',
                border: '1px solid var(--border-1)',
                borderRadius: 12,
                padding: 20,
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
                boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-1)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--success)' }}></span>
                    Target Location
                  </h3>
                  {/* Storage Segment Toggle */}
                  <div style={{
                    display: 'inline-flex',
                    background: 'var(--surface-3)',
                    borderRadius: 8,
                    padding: 2,
                    border: '1px solid var(--border-2)',
                  }}>
                    <button
                      type="button"
                      onClick={() => setTargetStorageType('local')}
                      style={{
                        padding: '4px 10px',
                        fontSize: 11,
                        fontWeight: 600,
                        borderRadius: 6,
                        border: 'none',
                        background: targetStorageType === 'local' ? 'var(--surface-1)' : 'transparent',
                        color: targetStorageType === 'local' ? 'var(--text-1)' : 'var(--text-3)',
                        cursor: 'pointer',
                        boxShadow: targetStorageType === 'local' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                        transition: 'all 0.1s',
                      }}
                    >
                      Local Device
                    </button>
                    <button
                      type="button"
                      onClick={() => setTargetStorageType('cloud')}
                      style={{
                        padding: '4px 10px',
                        fontSize: 11,
                        fontWeight: 600,
                        borderRadius: 6,
                        border: 'none',
                        background: targetStorageType === 'cloud' ? 'var(--surface-1)' : 'transparent',
                        color: targetStorageType === 'cloud' ? 'var(--text-1)' : 'var(--text-3)',
                        cursor: 'pointer',
                        boxShadow: targetStorageType === 'cloud' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                        transition: 'all 0.1s',
                      }}
                    >
                      Cloud Storage
                    </button>
                  </div>
                </div>

                {targetStorageType === 'local' ? (
                  <div>
                    <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 6 }}>
                      {inputLayout === 'folder' ? 'Local Folder Path' : 'Local File Path'}
                    </label>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input
                        type="text"
                        value={
                          inputLayout === 'folder'
                            ? targetFolder
                            : inputLayout === 'source-one-target-many'
                              ? targetMultiPaths.join(', ')
                              : targetPath
                        }
                        onChange={e => {
                          if (inputLayout === 'folder') setTargetFolder(e.target.value)
                          else if (inputLayout === 'source-one-target-many') setTargetMultiPaths(e.target.value.split(',').map(s => s.trim()).filter(Boolean))
                          else setTargetPath(e.target.value)
                        }}
                        placeholder={inputLayout === 'folder' ? 'e.g. /path/to/target_folder' : 'e.g. /path/to/target_file.csv'}
                        style={{
                          flex: 1,
                          height: 38,
                          borderRadius: 8,
                          border: '1px solid var(--border-2)',
                          background: 'var(--surface-2)',
                          color: 'var(--text-1)',
                          padding: '0 12px',
                          fontSize: 13,
                          outline: 'none',
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => {
                          setBrowserTarget('target')
                          setIsBrowserOpen(true)
                        }}
                        className="btn btn-secondary"
                        style={{ height: 38, padding: '0 14px', fontSize: 13, fontWeight: 600 }}
                      >
                        Browse...
                      </button>
                    </div>
                    {inputLayout === 'source-one-target-many' && targetMultiPaths.length > 0 && (
                      <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>
                        Selected {targetMultiPaths.length} target file(s)
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 4 }}>
                        Saved Connection (Optional)
                      </label>
                      <select
                        value={targetCloudConfig.connectionId || ''}
                        onChange={e => applySavedCloudConnection(setTargetCloudConfig, e.target.value)}
                        style={{
                          width: '100%',
                          height: 36,
                          borderRadius: 8,
                          border: '1px solid var(--border-2)',
                          background: 'var(--surface-2)',
                          color: 'var(--text-1)',
                          padding: '0 12px',
                          fontSize: 13,
                          outline: 'none',
                        }}
                      >
                        <option value="">-- Manual (paste JSON) --</option>
                        {savedCloudConnections.map((conn) => (
                          <option key={conn.id} value={conn.id}>
                            {conn.name} ({conn.bucket})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 4 }}>
                        Bucket Name
                      </label>
                      <input
                        type="text"
                        value={targetCloudConfig.bucket}
                        onChange={e => setTargetCloudConfig(prev => resolveCloudConfig({ ...prev, bucket: e.target.value }, savedCloudConnections))}
                        placeholder="my-gcs-bucket"
                        style={{
                          width: '100%',
                          height: 36,
                          borderRadius: 8,
                          border: '1px solid var(--border-2)',
                          background: 'var(--surface-2)',
                          color: 'var(--text-1)',
                          padding: '0 12px',
                          fontSize: 13,
                          outline: 'none',
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 4 }}>
                        Project ID (Optional)
                      </label>
                      <input
                        type="text"
                        value={targetCloudConfig.projectId}
                        onChange={e => setTargetCloudConfig(prev => ({ ...prev, projectId: e.target.value }))}
                        placeholder="my-gcs-project-id"
                        style={{
                          width: '100%',
                          height: 36,
                          borderRadius: 8,
                          border: '1px solid var(--border-2)',
                          background: 'var(--surface-2)',
                          color: 'var(--text-1)',
                          padding: '0 12px',
                          fontSize: 13,
                          outline: 'none',
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 4 }}>
                        Credentials JSON (Optional)
                      </label>
                      <textarea
                        value={targetCloudConfig.credentialsJson}
                        disabled={Boolean(targetCloudConfig.connectionId)}
                        onChange={e => setTargetCloudConfig(prev => ({ ...prev, connectionId: '', credentialsJson: e.target.value }))}
                        placeholder='{"type": "service_account", ...}'
                        style={{
                          width: '100%',
                          height: 50,
                          borderRadius: 8,
                          border: '1px solid var(--border-2)',
                          background: 'var(--surface-2)',
                          color: 'var(--text-1)',
                          padding: '8px 12px',
                          fontSize: 12,
                          outline: 'none',
                          resize: 'vertical',
                          opacity: targetCloudConfig.connectionId ? 0.6 : 1,
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', marginBottom: 4 }}>
                        {inputLayout === 'folder' ? 'Cloud Prefix (Folder)' : 'Object Name / Prefix'}
                      </label>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <input
                          type="text"
                          value={
                            inputLayout === 'folder'
                              ? targetCloudPrefix
                              : inputLayout === 'source-one-target-many'
                                ? targetMultiPaths.join(', ')
                                : targetCloudConfig.objectName
                          }
                          onChange={e => {
                            if (inputLayout === 'folder') setTargetCloudPrefix(e.target.value)
                            else if (inputLayout === 'source-one-target-many') setTargetMultiPaths(e.target.value.split(',').map(s => s.trim()).filter(Boolean))
                            else setTargetCloudConfig(prev => ({
                              ...prev,
                              objectName: normalizeGcsObjectName(prev.bucket, e.target.value),
                            }))
                          }}
                          placeholder="e.g. data/targets/"
                          style={{
                            flex: 1,
                            height: 38,
                            borderRadius: 8,
                            border: '1px solid var(--border-2)',
                            background: 'var(--surface-2)',
                            color: 'var(--text-1)',
                            padding: '0 12px',
                            fontSize: 13,
                            outline: 'none',
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            setBrowserTarget('target')
                            setIsBrowserOpen(true)
                          }}
                          className="btn btn-secondary"
                          style={{ height: 38, padding: '0 14px', fontSize: 13, fontWeight: 600 }}
                        >
                          Browse...
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Format detection status and continue bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: 20,
              borderTop: '1px solid var(--border-1)',
              gap: 16,
              flexWrap: 'wrap',
            }}>
              <div>
                {fileFormat && (
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 12px',
                    borderRadius: 20,
                    background: 'var(--accent-muted)',
                    border: '1px solid var(--accent-border)',
                    fontSize: 12,
                    fontWeight: 500,
                    color: 'var(--accent)',
                  }}>
                    <span>Detected Format: <strong style={{ textTransform: 'uppercase' }}>{fileFormat}</strong> {isManualFormat ? '(Manual override)' : '(Auto-detected)'}</span>
                    <button
                      type="button"
                      onClick={() => setIsFormatPopupOpen(true)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--text-2)',
                        cursor: 'pointer',
                        textDecoration: 'underline',
                        fontSize: 11,
                        padding: 0,
                        fontWeight: 600,
                      }}
                    >
                      Change
                    </button>
                  </div>
                )}
                {!fileFormat && (
                  <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                    Please select files to automatically detect format.
                  </div>
                )}
              </div>

              {/* Action button */}
              <button
                type="button"
                onClick={handleContinue}
                className="btn btn-primary"
                style={{ height: 40, padding: '0 24px', fontSize: 13, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <span>Continue</span>
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 6h6M6.5 3.5L9 6 6.5 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>

            {pairingError && (
              <div style={{
                marginTop: 16,
                padding: '10px 12px',
                borderRadius: 8,
                background: 'var(--danger-muted)',
                color: 'var(--danger)',
                fontSize: 12,
              }}>
                {pairingError}
              </div>
            )}
          </div>
        )}

        {/* Step 1a: Select Format */}
        {showFormatSelect && (
          <div style={{ animation: 'fade-in 0.2s ease' }}>
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
                Step 1 of 4
              </div>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 6 }}>
                What kind of files do you want to validate?
              </h2>
              <p style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.5 }}>
                Choose the validation format that matches your data files.
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(240px, 1fr))', gap: 16 }}>
              {/* CSV Option */}
              <button
                onClick={() => { setFileFormat('csv'); setStep(2); setSubPhase('input-layout') }}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  gap: 16,
                  padding: 24,
                  borderRadius: 12,
                  border: '1px solid var(--border-1)',
                  background: 'var(--surface-1)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'var(--accent-border)';
                  e.currentTarget.style.background = 'var(--accent-muted)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border-1)';
                  e.currentTarget.style.background = 'var(--surface-1)';
                }}
              >
                <div style={{
                  width: 42, height: 42,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  borderRadius: 10,
                  background: 'var(--accent)',
                  color: '#fff',
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <rect x="3" y="3" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/>
                    <path d="M7 7h6M7 10h6M7 13h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </div>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-1)', marginBottom: 6 }}>
                    CSV / Delimited File Validation
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.4, margin: 0 }}>
                    Standard tabular formats (CSV, TSV, pipes). Supports flexible headers, custom column mappings, footer checks, and email/numeric/date layout analyses.
                  </p>
                </div>
              </button>

              {/* ZIP Option */}
              <button
                onClick={() => { setFileFormat('zip'); setStep(2); setSubPhase('input-layout') }}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  gap: 16,
                  padding: 24,
                  borderRadius: 12,
                  border: '1px solid var(--border-1)',
                  background: 'var(--surface-1)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'var(--orange, #f59e0b)'
                  e.currentTarget.style.background = 'rgba(245, 158, 11, 0.05)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border-1)'
                  e.currentTarget.style.background = 'var(--surface-1)'
                }}
              >
                <div style={{
                  width: 42, height: 42,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  borderRadius: 10,
                  background: 'var(--orange, #f59e0b)',
                  color: '#fff',
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M5 4h10v12H5V4z" stroke="currentColor" strokeWidth="1.5"/>
                    <path d="M7 8h6M7 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    <path d="M6 4.5l2-2h4l2 2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-1)', marginBottom: 6 }}>
                    ZIP Archive Validation
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.4, margin: 0 }}>
                    Archive-first workflows keep the same frontend wizard and pair/folder layout, so ZIP can slot into the existing flow.
                  </p>
                </div>
              </button>

              {/* DAT Option */}
              <button
                onClick={() => { setFileFormat('dat'); setStep(2); setSubPhase('input-layout') }}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  gap: 16,
                  padding: 24,
                  borderRadius: 12,
                  border: '1px solid var(--border-1)',
                  background: 'var(--surface-1)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'var(--orange, #f59e0b)'
                  e.currentTarget.style.background = 'rgba(245, 158, 11, 0.05)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border-1)'
                  e.currentTarget.style.background = 'var(--surface-1)'
                }}
              >
                <div style={{
                  width: 42, height: 42,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  borderRadius: 10,
                  background: 'var(--orange, #f59e0b)',
                  color: '#fff',
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M5 4h10v12H5V4z" stroke="currentColor" strokeWidth="1.5"/>
                    <path d="M7 8h6M7 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    <path d="M6 4.5l2-2h4l2 2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-1)', marginBottom: 6 }}>
                    DAT File Validation
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.4, margin: 0 }}>
                    Frontend-only DAT flow that keeps the same wizard experience while normalizing to CSV for the backend.
                  </p>
                </div>
              </button>

              {/* Fixed Width Option */}
              <button
                onClick={() => { setFileFormat('fixed-width'); setStep(2); setSubPhase('input-layout') }}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  gap: 16,
                  padding: 24,
                  borderRadius: 12,
                  border: '1px solid var(--border-1)',
                  background: 'var(--surface-1)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'var(--blue, #3b82f6)';
                  e.currentTarget.style.background = 'rgba(59, 130, 246, 0.05)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border-1)';
                  e.currentTarget.style.background = 'var(--surface-1)';
                }}
              >
                <div style={{
                  width: 42, height: 42,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  borderRadius: 10,
                  background: 'var(--blue, #3b82f6)',
                  color: '#fff',
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <rect x="3" y="5" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5"/>
                    <path d="M6 5v10M10 5v10M14 5v10" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2 2"/>
                  </svg>
                </div>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-1)', marginBottom: 6 }}>
                    Fixed-Width Date Validation
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.4, margin: 0 }}>
                    Extremely fast low-memory streaming line-by-line validation for giant records. Slices and standardizes target/source date segments at specific character indices.
                  </p>
                </div>
              </button>

              <button
                onClick={() => { setFileFormat('json'); setStep(2); setSubPhase('input-layout') }}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  gap: 16,
                  padding: 24,
                  borderRadius: 12,
                  border: '1px solid var(--border-1)',
                  background: 'var(--surface-1)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'var(--emerald, #10b981)'
                  e.currentTarget.style.background = 'rgba(16, 185, 129, 0.05)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border-1)'
                  e.currentTarget.style.background = 'var(--surface-1)'
                }}
              >
                <div style={{
                  width: 42, height: 42,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  borderRadius: 10,
                  background: 'var(--emerald, #10b981)',
                  color: '#fff',
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M5 4h10v12H5V4z" stroke="currentColor" strokeWidth="1.5"/>
                    <path d="M7 8h6M7 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </div>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-1)', marginBottom: 6 }}>
                    JSON Document Validation
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.4, margin: 0 }}>
                    Compare two JSON files as whole documents. Key order and array element order are ignored
                    (canonical sort, like <code>json.dumps(..., sort_keys=True)</code>).
                  </p>
                </div>
              </button>
            </div>
          </div>
        )}

        {/* Step 1b: Select Storage */}
        {showInputLayout && (
          <StepInputLayout
            fileFormat={fileFormat}
            onBack={() => { setStep(1); setSubPhase('format-select') }}
            onNext={handleInputLayoutNext}
          />
        )}

        {showTypeSelect && (
          <div>
            <button
              onClick={() => { setStep(2); setSubPhase('input-layout') }}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                background: 'none', border: 'none', cursor: 'pointer',
                fontSize: 12, color: 'var(--text-3)', fontFamily: 'inherit',
                padding: '0 0 16px 0', transition: 'color 0.12s',
              }}
              onMouseEnter={e => e.currentTarget.style.color = 'var(--text-1)'}
              onMouseLeave={e => e.currentTarget.style.color = 'var(--text-3)'}
            >
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M9 6.5H3M5.5 4L3 6.5 5.5 9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Back to file format selection
            </button>
            <Step1_DataSource onNext={handleDataSourceNext} />
          </div>
        )}

        {/* Step 1b */}
        {showPickSource && (
          <Step2_FilePicker
            panelLabel="Source"
            storageType={sourceStorageType}
            value={sourcePath}
            cloudConfig={sourceCloudConfig}
            onCloudConfigChange={setSourceCloudConfig}
            onSelect={handleSourceSelected}
            onBack={() => setSubPhase('type-select')}
            disabled={pairingLoading}
            selectionMode={
              subPhase === 'pick-source-folder' ? 'folder'
                : subPhase === 'pick-source-multi' ? 'multi'
                  : 'file'
            }
            fileFormat={fileFormat}
          />
        )}

        {showPickTarget && (
          <Step2_FilePicker
            panelLabel="Target"
            storageType={targetStorageType}
            value={targetPath}
            cloudConfig={targetCloudConfig}
            onCloudConfigChange={setTargetCloudConfig}
            onSelect={handleTargetSelected}
            onBack={() => {
              if (subPhase === 'pick-target-folder') setSubPhase('pick-source-folder')
              else if (subPhase === 'pick-target-multi') setSubPhase('pick-source')
              else setSubPhase('pick-source')
            }}
            disabled={pairingLoading}
            selectionMode={
              subPhase === 'pick-target-folder' ? 'folder'
                : subPhase === 'pick-target-multi' ? 'multi'
                  : 'file'
            }
            fileFormat={fileFormat}
          />
        )}

        {pairingLoading && (
          <div style={{ padding: 16, fontSize: 13, color: 'var(--text-3)' }}>Matching files by name…</div>
        )}
        {pairingError && (
          <div style={{ padding: 12, borderRadius: 8, background: 'var(--danger-muted)', color: 'var(--danger)', fontSize: 12 }}>
            {pairingError}
          </div>
        )}

        {showFilePairing && (
          <>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-2)', marginBottom: 8 }}>
              <input
                type="checkbox"
                checked={recursiveFolderMatch}
                onChange={e => setRecursiveFolderMatch(e.target.checked)}
              />
              Include files in subfolders (recursive match by filename)
            </label>
            <StepFilePairing
            pairs={pairingState.pairs}
            unmatchedSources={pairingState.unmatchedSources}
            unmatchedTargets={pairingState.unmatchedTargets}
            onChange={setPairingState}
            onBack={() => setSubPhase('pick-target-folder')}
            onContinue={handlePairingComplete}
          />
          </>
        )}

        {/* Step 2: Configure */}
        {showConfigure && showBatchMappingModeChoice && (
          <StepBatchMappingMode
            pairCount={validationUnits.length}
            fileFormat={fileFormat}
            onSelect={handleBatchMappingModeSelect}
            onBack={() => {
              setStep(2)
              setSubPhase('file-pairing')
            }}
          />
        )}

        {showConfigure && !showBatchMappingModeChoice && (
          <>
            {showTemplateMapping && (
              <div style={{
                marginBottom: 16,
                padding: '14px 16px',
                borderRadius: 10,
                border: '1px solid var(--accent-border)',
                background: 'var(--accent-muted)',
              }}>
                <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--accent)' }}>
                  {fileFormat === 'json'
                    ? 'Shared JSON validation'
                    : fileFormat === 'fixed-width'
                      ? 'Shared fixed-width layout'
                      : 'Shared mapping template'}
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 8, marginBottom: 0, lineHeight: 1.5 }}>
                  {fileFormat === 'json' ? (
                    <>
                      All {validationUnits.length} pairs will use semantic JSON comparison (sorted keys, multiset arrays).
                      Click apply below to confirm every pair, or change strategy to review each pair individually.
                    </>
                  ) : (
                    <>
                      Configure using the first pair (
                      <code style={{ fontFamily: 'Geist Mono, monospace' }}>
                        {validationUnits[0]?.sourcePaths?.[0]?.split('/').pop()}
                      </code>
                      {' → '}
                      <code style={{ fontFamily: 'Geist Mono, monospace' }}>
                        {validationUnits[0]?.targetPaths?.[0]?.split('/').pop()}
                      </code>
                      ), then apply to all {validationUnits.length} pairs.
                      {fileFormat === 'fixed-width'
                        ? ' Field slice positions are re-detected per file; only pairs whose fields do not match need manual setup.'
                        : ' Only files with column mismatches will need manual mapping.'}
                    </>
                  )}
                </p>
              </div>
            )}

            {batchColumnMappingMode === 'template-fixups' && (
              <div style={{
                marginBottom: 16,
                padding: '12px 14px',
                borderRadius: 10,
                border: '1px solid var(--border-1)',
                background: 'var(--surface-2)',
              }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)', marginBottom: 6 }}>
                  {validationUnits.length - batchMismatchUnitIds.length} of {validationUnits.length} file
                  {fileFormat === 'fixed-width' ? ' pairs matched the layout' : ' pairs matched the template'}
                  {' '}automatically
                </div>
                <p style={{ fontSize: 12, color: 'var(--text-3)', margin: '0 0 8px', lineHeight: 1.45 }}>
                  {fileFormat === 'fixed-width' ? 'Configure' : 'Map'} the remaining {batchMismatchUnitIds.length} file pair{batchMismatchUnitIds.length === 1 ? '' : 's'} below.
                </p>
                {activeUnitId && Array.isArray(batchMismatchDetails[activeUnitId]) && batchMismatchDetails[activeUnitId].length > 0 && (
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--danger)' }}>
                    {batchMismatchDetails[activeUnitId].map(issue => (
                      <li key={issue} style={{ marginBottom: 4 }}>{issue}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {sequentialBatchMapping && (
              <div style={{
                marginBottom: 20,
                padding: '14px 16px',
                borderRadius: 10,
                border: '1px solid var(--border-1)',
                background: 'var(--surface-2)',
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                  marginBottom: 12,
                }}>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)' }}>
                      {batchColumnMappingMode === 'template-fixups'
                        ? `Manual fix — file ${activeUnitIndex + 1} of ${mappingQueueUnits.length}`
                        : `Column mapping — file pair ${activeUnitIndex + 1} of ${mappingQueueUnits.length}`}
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)', marginTop: 4 }}>
                      {activeUnit?.sourcePaths?.[0]?.split('/').pop() ?? 'Source'}
                      {' → '}
                      {activeUnit?.targetPaths?.[0]?.split('/').pop() ?? 'Target'}
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-3)', whiteSpace: 'nowrap' }}>
                    {validationUnits.filter(u => isUnitMappingConfigured(u.unitId)).length} / {validationUnits.length} mapped
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {mappingQueueUnits.map((unit, index) => {
                    const isActive = unit.unitId === activeUnitId
                    const isDone = isUnitMappingConfigured(unit.unitId)
                    const srcName = unit.sourcePaths[0]?.split('/').pop() || 'source'
                    const tgtName = unit.targetPaths[0]?.split('/').pop() || 'target'
                    return (
                      <button
                        key={unit.unitId}
                        type="button"
                        onClick={() => goToPairAtIndex(index)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 10,
                          width: '100%',
                          padding: '8px 10px',
                          borderRadius: 8,
                          border: isActive ? '1px solid var(--accent-border)' : '1px solid var(--border-1)',
                          background: isActive ? 'var(--accent-muted)' : 'var(--surface-1)',
                          cursor: 'pointer',
                          textAlign: 'left',
                          fontFamily: 'inherit',
                        }}
                      >
                        <span style={{
                          width: 22,
                          height: 22,
                          borderRadius: '50%',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 11,
                          fontWeight: 700,
                          flexShrink: 0,
                          background: isDone ? 'var(--success-muted)' : isActive ? 'var(--accent)' : 'var(--surface-3)',
                          color: isDone ? 'var(--success)' : isActive ? '#fff' : 'var(--text-4)',
                          border: isDone ? '1px solid rgba(34,197,94,0.3)' : '1px solid var(--border-2)',
                        }}>
                          {isDone ? '✓' : index + 1}
                        </span>
                        <span style={{ flex: 1, fontSize: 12, color: 'var(--text-2)' }}>
                          <span style={{ fontFamily: 'Geist Mono, monospace', color: 'var(--text-1)' }}>{srcName}</span>
                          {' → '}
                          <span style={{ fontFamily: 'Geist Mono, monospace', color: 'var(--text-1)' }}>{tgtName}</span>
                        </span>
                        {isActive && (
                          <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase' }}>
                            Current
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
                <p style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 10, marginBottom: 0 }}>
                  {batchColumnMappingMode === 'template-fixups'
                    ? (fileFormat === 'fixed-width'
                      ? 'Fix layout for each file pair that did not match the shared template, then continue.'
                      : 'Fix mapping for each file that did not match the shared template, then continue.')
                    : (fileFormat === 'json'
                      ? 'Confirm each pair, then continue. You can return to earlier pairs from the list above.'
                      : fileFormat === 'fixed-width'
                        ? 'Configure fields for this pair, then continue. You can return to earlier pairs from the list above.'
                        : 'Map columns for this pair, then continue to the next file. You can return to earlier pairs from the list above.')}
                </p>
              </div>
            )}
            {isBatchMode && activeUnit && !sequentialBatchMapping && (
              <p style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 12 }}>
                Source: {activeUnit.sourcePaths.map(p => p.split('/').pop()).join(', ')}
                {' → '}
                Target: {activeUnit.targetPaths.map(p => p.split('/').pop()).join(', ')}
                {(activeUnit.sourcePaths.length > 1 || activeUnit.targetPaths.length > 1) && (
                  <span style={{ color: 'var(--text-4)' }}> (merged before validate)</span>
                )}
              </p>
            )}
            {fileFormat === 'json' ? (
              <div style={{
                padding: 20,
                borderRadius: 12,
                border: '1px solid var(--border-1)',
                background: 'var(--surface-1)',
              }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-1)', marginBottom: 8 }}>
                  JSON semantic comparison
                </h3>
                <p style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.5, margin: 0 }}>
                  Source: <code>{sourceDisplay}</code><br />
                  Target: <code>{targetDisplay}</code>
                </p>
                <p style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.5, marginTop: 12, marginBottom: 0 }}>
                  Objects are compared with sorted keys; arrays are compared as sorted multisets of elements.
                  No UID column or delimiter is required.
                </p>
              </div>
            ) : isCsvLikeFormat(fileFormat) ? (
              <Step3_Configure
                sourcePath={sourceDisplay}
                targetPath={targetDisplay}
                sourceColumns={columnPreview.sourceColumns}
                targetColumns={columnPreview.targetColumns.filter(col => col !== uidColumn.trim())}
                compareColumns={columnPreview.compareColumns}
                previewLoading={columnPreviewLoading}
                previewError={columnPreviewError}
                unmatchedSourceColumns={columnPreview.unmatchedSourceColumns}
                unmatchedTargetColumns={columnPreview.unmatchedTargetColumns}
                mappings={mappings}
                onMappingChange={setMappings}
                uidColumn={uidColumn}
                onUidColumnChange={setUidColumn}
                hasHeader={hasHeader}
                onHasHeaderChange={checked => {
                  setHasHeader(checked)
                  setUidColumn(checked ? 'id' : 'column_1')
                }}
                sourceSamples={columnPreview.sourceSamples}
                targetSamples={columnPreview.targetSamples}
                sampleRowCount={columnPreview.sampleRowCount}
                delimiter={delimiter}
                resolvedDelimiter={columnPreview.delimiter}
                onDelimiterChange={setDelimiter}
                validateHeaderFormats={validateHeaderFormats}
                onValidateHeaderFormatsChange={setValidateHeaderFormats}
                validateFooters={validateFooters}
                onValidateFootersChange={setValidateFooters}
                headerLeadingRows={headerLeadingRows}
                onHeaderLeadingRowsChange={setHeaderLeadingRows}
                footerTrailingRows={footerTrailingRows}
                onFooterTrailingRowsChange={setFooterTrailingRows}
                testMode={testMode}
                onTestModeChange={setTestMode}
                uidGte={uidGte}
                onUidGteChange={setUidGte}
                formatCheckBySource={formatCheckBySource(formatChecks)}
                analyzeLoading={analyzeLoading}
                analyzeError={analyzeError}
                footerValidation={footerValidation}
              />
            ) : (
              <FixedWidthConfigurator
                sourcePath={sourceDisplay}
                targetPath={targetDisplay}
                columns={fwColumns}
                setColumns={setFwColumns}
                joinColumn={fwJoinColumn}
                setJoinColumn={setFwJoinColumn}
                matchStrategy={fwMatchStrategy}
                setMatchStrategy={setFwMatchStrategy}
                dateColumn={fwDateColumn}
                setDateColumn={setFwDateColumn}
                layoutLoading={fwLayoutLoading}
                layoutError={fwLayoutError}
                sourceSample={fwSourceSample}
                targetSample={fwTargetSample}
                sourceDateStart={sourceDateStart}
                setSourceDateStart={setSourceDateStart}
                sourceDateEnd={sourceDateEnd}
                setSourceDateEnd={setSourceDateEnd}
                sourceDateFormat={sourceDateFormat}
                setSourceDateFormat={setSourceDateFormat}
                targetDateStart={targetDateStart}
                setTargetDateStart={setTargetDateStart}
                targetDateEnd={targetDateEnd}
                setTargetDateEnd={setTargetDateEnd}
                targetDateFormat={targetDateFormat}
                setTargetDateFormat={setTargetDateFormat}
              />
            )}
            {batchApplyAllError && (
              <div style={{
                marginTop: 12,
                padding: '10px 12px',
                borderRadius: 8,
                background: 'var(--danger-muted)',
                color: 'var(--danger)',
                fontSize: 12,
              }}>
                {batchApplyAllError}
              </div>
            )}

            <div style={{ marginTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <button
                type="button"
                onClick={handleConfigureBack}
                className="btn btn-ghost"
                disabled={batchApplyAllLoading}
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M9 6H3M5.5 3.5L3 6l2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                {sequentialBatchMapping && activeUnitIndex > 0
                  ? 'Previous pair'
                  : showTemplateMapping
                    ? 'Change strategy'
                    : 'Back'}
              </button>
              {showTemplateMapping ? (
                <button
                  type="button"
                  onClick={handleApplyTemplateToAll}
                  disabled={batchApplyAllLoading || !isCurrentPairMappingValid()}
                  className="btn btn-primary"
                >
                  {batchApplyAllLoading
                    ? 'Applying to all files…'
                    : fileFormat === 'json'
                      ? `Apply to all ${validationUnits.length} pairs`
                      : fileFormat === 'fixed-width'
                        ? `Apply layout to all ${validationUnits.length} files`
                        : `Apply mapping to all ${validationUnits.length} files`}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleConfigureContinue}
                  disabled={(sequentialBatchMapping || showTemplateMapping) && !isCurrentPairMappingValid()}
                  className="btn btn-primary"
                >
                  {sequentialBatchMapping && activeUnitIndex >= 0 && activeUnitIndex < mappingQueueUnits.length - 1
                    ? batchColumnMappingMode === 'template-fixups'
                      ? `Save & next (${activeUnitIndex + 2} of ${mappingQueueUnits.length})`
                      : `Save & next pair (${activeUnitIndex + 2} of ${mappingQueueUnits.length})`
                    : 'Review & run'}
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M3 6h6M6.5 3.5L9 6l-2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
              )}
            </div>
          </>
        )}

        {/* Step 3: Review */}
        {showReview && (
          <div style={{ animation: 'fade-in 0.2s ease' }}>
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
                Step 4 of 4
              </div>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 4 }}>
                Review & Run
              </h2>
              <p style={{ fontSize: 13, color: 'var(--text-3)' }}>
                Confirm your selections, then validate or save as a draft.
              </p>
            </div>

            {/* File summary */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
              {[
                { label: 'Source file', value: sourceDisplay, accent: 'var(--accent)' },
                { label: 'Target file', value: targetDisplay, accent: 'var(--blue)' },
              ].map(({ label, value, accent }) => (
                <div key={label} style={{
                  padding: '12px 14px', borderRadius: 9,
                  background: 'var(--surface-2)', borderLeft: `3px solid ${accent}`,
                  border: `1px solid var(--border-1)`,
                }}>
                  <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 5 }}>
                    {label}
                  </div>
                  <code style={{
                    display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    fontSize: 12, color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace',
                  }} title={value}>
                    {value || '—'}
                  </code>
                </div>
              ))}
            </div>

            {isBatchMode && phase === 'idle' && (
              <div style={{ marginBottom: 16, padding: 14, borderRadius: 10, border: '1px solid var(--border-1)', background: 'var(--surface-2)' }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', marginBottom: 8 }}>
                  Batch: {validationUnits.length} validation unit{validationUnits.length === 1 ? '' : 's'}
                </div>
                <ul style={{ margin: '0 0 12px', paddingLeft: 18, fontSize: 12, color: 'var(--text-3)' }}>
                  {validationUnits.map(u => (
                    <li key={u.unitId} style={{ marginBottom: 4 }}>
                      {u.label || u.sourcePaths.map(p => p.split('/').pop()).join(' + ')}
                      {' → '}
                      {u.targetPaths.map(p => p.split('/').pop()).join(' + ')}
                    </li>
                  ))}
                </ul>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-4)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  When a file pair fails
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    className={onUnitFailure === 'continue' ? 'btn btn-primary' : 'btn btn-secondary'}
                    style={{ height: 32, fontSize: 12 }}
                    onClick={() => setOnUnitFailure('continue')}
                  >
                    Run all pairs
                  </button>
                  <button
                    type="button"
                    className={onUnitFailure === 'stop' ? 'btn btn-primary' : 'btn btn-secondary'}
                    style={{ height: 32, fontSize: 12 }}
                    onClick={() => setOnUnitFailure('stop')}
                  >
                    Stop on first failure
                  </button>
                </div>
              </div>
            )}

            {/* Config summary */}
            {isCsvLikeFormat(fileFormat) ? (
              <div style={{
                display: 'flex', gap: 16, padding: '10px 14px', borderRadius: 9,
                background: 'var(--surface-2)', border: '1px solid var(--border-1)',
                fontSize: 12, color: 'var(--text-3)', marginBottom: 12, flexWrap: 'wrap',
              }}>
                <span>UID: <strong style={{ color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace' }}>{uidColumn || '—'}</strong></span>
                <span>Delimiter: <strong style={{ color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace' }}>{columnPreview.delimiter || delimiter}</strong></span>
                <span>Header row: <strong style={{ color: 'var(--text-1)' }}>{hasHeader ? 'yes' : 'no (positional)'}</strong></span>
                <span>Columns mapped: <strong style={{ color: 'var(--text-1)' }}>{mappings.filter(m => m.targetCol).length} / {mappings.length || '—'}</strong></span>
              </div>
            ) : (
              <div style={{
                display: 'flex', gap: 16, padding: '10px 14px', borderRadius: 9,
                background: 'var(--surface-2)', border: '1px solid var(--border-1)',
                fontSize: 12, color: 'var(--text-3)', marginBottom: 12, flexWrap: 'wrap',
              }}>
                <span>Format: <strong style={{ color: 'var(--text-1)' }}>Fixed-Width</strong></span>
                <span>Match by: <strong style={{ color: 'var(--text-1)' }}>{fwJoinColumn}</strong> ({fwMatchStrategy})</span>
                <span>Columns: <strong style={{ color: 'var(--text-1)' }}>{fwColumns.map(c => c.field_name).join(', ')}</strong></span>
                <span>Date: <strong style={{ color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace' }}>{fwDateColumn} [{sourceDateStart}:{sourceDateEnd}]</strong></span>
              </div>
            )}

            {isCsvLikeFormat(fileFormat) && (
              <ResolvedDelimiterNotice
                requestedDelimiter={delimiter}
                resolvedDelimiter={columnPreview.delimiter}
              />
            )}

            {isCsvLikeFormat(fileFormat) && uidColumn.trim() && (
              <MappingColumnPreview
                uidColumn={uidColumn}
                hasHeader={hasHeader}
                mappings={mappings}
                sourceSamples={columnPreview.sourceSamples}
                targetSamples={columnPreview.targetSamples}
                sampleRowCount={columnPreview.sampleRowCount}
              />
            )}

            {isCsvLikeFormat(fileFormat) && (
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block' }}>
                  <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 5 }}>
                    Override delimiter (optional)
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <input
                      type="text"
                      value={delimiter}
                      onChange={e => setDelimiter(e.target.value)}
                      placeholder="auto"
                      className="input input-mono"
                      style={{ maxWidth: 160 }}
                    />
                    <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
                      Change only if the detected delimiter above is wrong; column preview will refresh.
                    </span>
                  </div>
                </label>
              </div>
            )}

            {/* Running state */}
            {phase === 'running' && (
              <div style={{
                marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10,
                padding: '11px 14px', borderRadius: 9,
                background: 'var(--accent-muted)', border: '1px solid var(--accent-border)',
              }}>
                <span style={{
                  width: 14, height: 14, borderRadius: '50%',
                  border: '2px solid var(--accent-border)', borderTopColor: 'var(--accent)',
                  animation: 'spin 0.7s linear infinite', display: 'inline-block', flexShrink: 0,
                }} />
                <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--accent)' }}>
                  Validating… ({jobProgress.phase})
                </span>
              </div>
            )}

            {/* Success */}
            {phase === 'success' && result && (result.mapping_format_checks?.length > 0 || result.footer_validation) && (
              <div style={{
                marginBottom: 12, padding: '12px 14px', borderRadius: 9,
                background: 'var(--surface-2)', border: '1px solid var(--border-1)',
                fontSize: 12, color: 'var(--text-2)',
              }}>
                {result.mapping_format_checks?.length > 0 && (
                  <div style={{ marginBottom: 8 }}>
                    <strong style={{ color: 'var(--text-1)' }}>Format checks:</strong>{' '}
                    {result.mapping_format_checks.filter(c => !c.compatible).length > 0
                      ? `${result.mapping_format_checks.filter(c => !c.compatible).length} warning(s)`
                      : 'all mapped columns compatible'}
                  </div>
                )}
                {result.footer_validation && (
                  <div style={{ color: result.footer_validation.match ? 'var(--success)' : 'var(--danger)' }}>
                    Footer: {result.footer_validation.match ? 'match' : (result.footer_validation.message || 'mismatch')}
                  </div>
                )}
              </div>
            )}

            {phase === 'success' && result && (
              <div style={{
                marginBottom: 12, padding: '14px 16px', borderRadius: 9,
                background: 'var(--success-muted)', border: '1px solid rgba(34,197,94,0.25)',
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--success)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                    <path d="M2 6.5l3 3 6-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Validation complete
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                  <StatCard label="Match" value={result.summary?.is_match ? 'Yes' : 'No'} accent={result.summary?.is_match ? 'var(--success)' : 'var(--danger)'} />
                  <StatCard label={fileFormat === 'fixed-width' ? 'Lines compared' : fileFormat === 'json' ? 'Documents' : 'Source rows'} value={result.summary?.source_row_count ?? '—'} />
                  <StatCard label={fileFormat === 'fixed-width' ? 'Target lines' : fileFormat === 'json' ? 'Compared' : 'Target rows'} value={result.summary?.target_row_count ?? '—'} />
                  <StatCard label="Mismatches" value={result.summary?.total_mismatch_records ?? '—'} accent={result.summary?.total_mismatch_records > 0 ? 'var(--danger)' : undefined} />
                </div>
                {result.test_mode === 'litmus' && result.litmus && (
                  <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-3)' }}>
                    Litmus checks passed: {result.litmus.checks_passed?.length ?? 0} / {result.litmus.checks_run?.length ?? 0}
                    {(result.litmus.checks_failed?.length ?? 0) > 0 && (
                      <div style={{ marginTop: 4, color: 'var(--danger)' }}>
                        Failed checks: {result.litmus.checks_failed.join(', ')}
                      </div>
                    )}
                  </div>
                )}
                {result.test_mode !== 'litmus' && (
                  <button
                    type="button"
                    onClick={() => navigate('/report', { state: { result } })}
                    style={{
                      marginTop: 12,
                      width: '100%',
                      height: 38,
                      borderRadius: 8,
                      border: '1px solid var(--border-1)',
                      background: 'var(--surface-1)',
                      color: 'var(--text-1)',
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    View Detailed Report
                  </button>
                )}
              </div>
            )}

            {batchResult && (
              <div style={{
                marginBottom: 12, padding: '14px 16px', borderRadius: 9,
                background: batchResult.summary?.is_match ? 'var(--success-muted)' : 'var(--surface-2)',
                border: `1px solid ${batchResult.summary?.is_match ? 'rgba(34,197,94,0.25)' : 'var(--border-1)'}`,
              }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)', marginBottom: 10 }}>
                  Batch results — {batchResult.summary.passed_units}/{batchResult.summary.total_units} passed
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 12 }}>
                  <StatCard label="Completed" value={batchResult.summary.completed_units} />
                  <StatCard label="Failed" value={batchResult.summary.failed_units} accent={batchResult.summary.failed_units ? 'var(--danger)' : undefined} />
                  <StatCard label="Skipped" value={batchResult.summary.skipped_units} />
                  <StatCard label="All match" value={batchResult.summary.is_match ? 'Yes' : 'No'} accent={batchResult.summary.is_match ? 'var(--success)' : 'var(--danger)'} />
                </div>
                {batchResult.units?.map(unit => (
                  <div
                    key={unit.unit_id}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: '1px solid var(--border-1)',
                      marginBottom: 6,
                      fontSize: 12,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <code style={{ fontFamily: 'Geist Mono, monospace', color: 'var(--text-2)' }}>
                        {unit.source_paths?.map(p => p.split('/').pop()).join(' + ')}
                        {' → '}
                        {unit.target_paths?.map(p => p.split('/').pop()).join(' + ')}
                      </code>
                      <span style={{
                        fontWeight: 600,
                        color: unit.status === 'completed' && unit.result?.summary?.is_match
                          ? 'var(--success)'
                          : unit.status === 'completed' ? 'var(--danger)' : 'var(--text-4)',
                      }}>
                        {unit.status}
                      </span>
                    </div>
                    {unit.error && (
                      <p style={{ margin: '6px 0 0', color: 'var(--danger)' }}>{unit.error}</p>
                    )}
                    {unit.result?.summary && (
                      <p style={{ margin: '6px 0 0', color: 'var(--text-3)' }}>
                        Mismatches: {unit.result.summary.total_mismatch_records ?? 0}
                      </p>
                    )}
                    {unit.status === 'completed' && unit.result && (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ marginTop: 8, height: 28, fontSize: 11 }}
                        onClick={() => navigate('/report', {
                          state: {
                            result: unit.result,
                            reportTitle: `${unit.source_paths?.map(p => p.split('/').pop()).join(' + ')} → ${unit.target_paths?.map(p => p.split('/').pop()).join(' + ')}`,
                          },
                        })}
                      >
                        View detailed report
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Error */}
            {phase === 'error' && (
              <div style={{
                marginBottom: 12, padding: '11px 14px', borderRadius: 9,
                background: 'var(--danger-muted)', border: '1px solid var(--danger-border)',
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--danger)', marginBottom: 4 }}>Validation failed</div>
                <p style={{ fontSize: 12, color: 'var(--text-2)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{errorMsg}</p>
              </div>
            )}

            {/* Back */}
            <button
              type="button"
              onClick={() => { setStep(3); setPhase('idle') }}
              className="btn btn-ghost"
              style={{ marginBottom: 4 }}
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M9 6H3M5.5 3.5L3 6l2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Back to Configure
            </button>

            <ActionBar
              onValidate={() => setParallelModalOpen(true)}
              onSaveAsDraft={handleSaveAsDraft}
              isValid={isValidForRun}
              isRunning={isRunning}
            />
          </div>
        )}
      </div>

      <ParallelValidationModal
        open={parallelModalOpen}
        onClose={() => setParallelModalOpen(false)}
        onConfirm={async () => {
          await handleValidate()
          return true
        }}
      />

      {/* Redesign Overlay Modals */}
      {isBrowserOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          animation: 'fade-in 0.15s ease',
        }}>
          <div style={{
            background: 'var(--surface-1)',
            border: '1px solid var(--border-1)',
            borderRadius: 16,
            width: '90%',
            maxWidth: 800,
            maxHeight: '90vh',
            overflowY: 'auto',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)',
            display: 'flex',
            flexDirection: 'column',
          }}>
            {/* Modal Header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '16px 24px',
              borderBottom: '1px solid var(--border-1)',
            }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-1)', margin: 0 }}>
                Browse Server Files ({browserTarget === 'source' ? 'Source' : 'Target'})
              </h3>
              <button
                type="button"
                onClick={() => setIsBrowserOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-3)',
                  cursor: 'pointer',
                  fontSize: 20,
                  fontWeight: 'bold',
                  lineHeight: 1,
                  padding: 4,
                }}
              >
                &times;
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '24px 24px 16px 24px', flex: 1, overflowY: 'auto' }}>
              <Step2_FilePicker
                panelLabel={browserTarget === 'source' ? 'Source' : 'Target'}
                storageType={browserTarget === 'source' ? sourceStorageType : targetStorageType}
                value={browserTarget === 'source' ? (inputLayout === 'folder' ? sourceFolder : sourcePath) : (inputLayout === 'folder' ? targetFolder : targetPath)}
                cloudConfig={browserTarget === 'source' ? sourceCloudConfig : targetCloudConfig}
                onCloudConfigChange={browserTarget === 'source' ? setSourceCloudConfig : setTargetCloudConfig}
                onSelect={browserTarget === 'source' ? handleSourceBrowserSelect : handleTargetBrowserSelect}
                onBack={() => setIsBrowserOpen(false)}
                disabled={pairingLoading}
                selectionMode={
                  inputLayout === 'folder' ? 'folder'
                    : browserTarget === 'source' && inputLayout === 'source-many-target-one' ? 'multi'
                    : browserTarget === 'target' && inputLayout === 'source-one-target-many' ? 'multi'
                    : 'file'
                }
                fileFormat={fileFormat}
              />
            </div>
          </div>
        </div>
      )}

      {isFormatPopupOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          animation: 'fade-in 0.15s ease',
        }}>
          <div style={{
            background: 'var(--surface-1)',
            border: '1px solid var(--border-1)',
            borderRadius: 16,
            width: '90%',
            maxWidth: 500,
            padding: 24,
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)',
            position: 'relative',
          }}>
            {/* Close button */}
            <button
              type="button"
              onClick={() => {
                setIsFormatPopupOpen(false)
                setPendingTransition(false)
              }}
              style={{
                position: 'absolute',
                top: 16,
                right: 16,
                background: 'none',
                border: 'none',
                color: 'var(--text-3)',
                cursor: 'pointer',
                fontSize: 20,
                fontWeight: 'bold',
              }}
            >
              &times;
            </button>

            <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-1)', marginTop: 0, marginBottom: 8, letterSpacing: '-0.02em' }}>
              Select File Format
            </h3>
            <p style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.5, marginBottom: 20 }}>
              {!fileFormat || pendingTransition
                ? "We couldn't automatically detect the file format from the selected paths. Please manually select a file format below to proceed."
                : "Choose the file format to apply for mapping and validation."}
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
              {[
                { id: 'csv', label: 'CSV / TSV Flat Files', desc: 'Delimiter-separated tabular files (comma, tab, pipe, semicolon, etc.)' },
                { id: 'fixed-width', label: 'Fixed-Width Files', desc: 'Files where columns have a fixed character length' },
                { id: 'json', label: 'JSON Document', desc: 'Compare and validate structured JSON documents' },
              ].map(opt => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => {
                    setFileFormat(opt.id)
                    setIsManualFormat(true)
                    setIsFormatPopupOpen(false)
                    if (pendingTransition) {
                      executeTransition(opt.id)
                    }
                  }}
                  style={{
                    textAlign: 'left',
                    padding: '12px 16px',
                    borderRadius: 10,
                    border: fileFormat === opt.id ? '2px solid var(--accent)' : '1px solid var(--border-2)',
                    background: fileFormat === opt.id ? 'var(--accent-muted)' : 'var(--surface-2)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                  }}
                  onMouseEnter={e => {
                    if (fileFormat !== opt.id) e.currentTarget.style.borderColor = 'var(--text-3)'
                  }}
                  onMouseLeave={e => {
                    if (fileFormat !== opt.id) e.currentTarget.style.borderColor = 'var(--border-2)'
                  }}
                >
                  <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>{opt.label}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.3 }}>{opt.desc}</span>
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
              <button
                type="button"
                onClick={() => {
                  setIsFormatPopupOpen(false)
                  setPendingTransition(false)
                }}
                className="btn btn-ghost"
                style={{ padding: '0 16px', height: 36, fontSize: 13 }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
