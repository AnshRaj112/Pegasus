import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatJobError } from '../../api/formatError.js'
import StepIndicator    from './StepIndicator'
import Step1_DataSource from './Step1_DataSource'
import Step2_FilePicker from './Step2_FilePicker'
import Step3_Configure  from './Step3_Configure'
import StepInputLayout from './StepInputLayout'
import StepFilePairing from './StepFilePairing'
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
  bucket: '',
  objectName: '',
  credentialsJson: '',
  projectId: '',
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

function buildStoragePayload(prefix, storageType, path, cloudConfig) {
  if (storageType === 'cloud') {
    return {
      [`${prefix}_cloud`]: {
        provider: String(cloudConfig?.provider || 'google-cloud-storage').trim() || 'google-cloud-storage',
        bucket: String(cloudConfig?.bucket || '').trim(),
        object_name: String(cloudConfig?.objectName || '').trim(),
        credentials_json: String(cloudConfig?.credentialsJson || ''),
        project_id: String(cloudConfig?.projectId || '').trim() || undefined,
      },
    }
  }
  return { [`${prefix}_path`]: String(path || '').trim() }
}

function isStorageSelectionComplete(storageType, path, cloudConfig) {
  if (storageType === 'cloud') {
    return Boolean(
      String(cloudConfig?.bucket || '').trim()
      && String(cloudConfig?.objectName || '').trim()
      && String(cloudConfig?.credentialsJson || '').trim(),
    )
  }
  return Boolean(String(path || '').trim())
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
  const [subPhase, setSubPhase] = useState('format-select')
  const [sourceStorageType, setSourceStorageType] = useState(null)
  const [targetStorageType, setTargetStorageType] = useState(null)
  const [sourcePath, setSourcePath] = useState('')
  const [targetPath, setTargetPath] = useState('')
  const [sourceCloudConfig, setSourceCloudConfig] = useState(DEFAULT_CLOUD_CONFIG)
  const [targetCloudConfig, setTargetCloudConfig] = useState(DEFAULT_CLOUD_CONFIG)
  const [fileFormat, setFileFormat] = useState('csv')
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
  const [footerTrailingRows, setFooterTrailingRows] = useState(1)
  const [formatChecks, setFormatChecks] = useState([])
  const [footerValidation, setFooterValidation] = useState(null)
  const [analyzeLoading, setAnalyzeLoading] = useState(false)
  const [analyzeError, setAnalyzeError] = useState('')

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

  const isBatchMode = inputLayout !== 'pair'
  const activeUnit = validationUnits.find(u => u.unitId === activeUnitId) || validationUnits[0] || null
  const effectiveSourcePath = isBatchMode ? (activeUnit?.sourcePaths?.[0] || '') : sourcePath
  const effectiveTargetPath = isBatchMode ? (activeUnit?.targetPaths?.[0] || '') : targetPath

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
    setFooterTrailingRows(detail.footer_trailing_rows || 1)

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
    setStep(targetStep)
    if (targetStep === 2) {
      setSubPhase('pick-source')
    } else if (targetStep === 4) {
      setSubPhase('type-select')
    }
    if (error) {
      setAnalyzeError(error)
      setColumnPreviewError(error)
    }

    queueMicrotask(() => onResetInitialData())
  }, [initialMappingData, onResetInitialData])



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
        footerTrailingRows,
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
      return
    }
    setMappings(cfg.mappings || [])
    setUidColumn(cfg.uidColumn || 'id')
    setDelimiter(cfg.delimiter || 'auto')
    setHasHeader(cfg.hasHeader !== false)
    setValidateHeaderFormats(cfg.validateHeaderFormats || false)
    setValidateFooters(cfg.validateFooters || false)
    setFooterTrailingRows(cfg.footerTrailingRows || 1)
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
    }
  }

  function switchActiveUnit(unitId) {
    persistActiveUnitConfig()
    setActiveUnitId(unitId)
    loadUnitConfig(unitId)
  }

  const activeUnitIndex = validationUnits.findIndex(u => u.unitId === activeUnitId)
  const sequentialBatchMapping = isBatchMode && validationUnits.length > 1

  function isCurrentPairMappingValid() {
    if (fileFormat === 'json') return true
    if (fileFormat === 'fixed-width') {
      return fwColumns.length > 0 && !!fwJoinColumn && !!sourceDateFormat.trim() && !!targetDateFormat.trim()
    }
    return !!uidColumn.trim() && mappings.some(row => String(row.targetCol || '').trim())
  }

  function isUnitMappingConfigured(unitId) {
    if (unitId === activeUnitId) return isCurrentPairMappingValid()
    const cfg = unitConfigs[unitId]
    if (!cfg) return false
    if (fileFormat === 'json') return true
    if (fileFormat === 'fixed-width') {
      return (cfg.fwColumns?.length ?? 0) > 0 && !!cfg.fwJoinColumn
    }
    const uid = String(cfg.uidColumn || '').trim()
    const rows = Array.isArray(cfg.mappings) ? cfg.mappings : []
    return !!uid && rows.some(row => String(row.targetCol || '').trim())
  }

  function goToPairAtIndex(index) {
    if (index < 0 || index >= validationUnits.length) return
    persistActiveUnitConfig()
    const unit = validationUnits[index]
    setActiveUnitId(unit.unitId)
    loadUnitConfig(unit.unitId)
  }

  function handleConfigureContinue() {
    if (sequentialBatchMapping && !isCurrentPairMappingValid()) return
    persistActiveUnitConfig()
    if (sequentialBatchMapping && activeUnitIndex >= 0 && activeUnitIndex < validationUnits.length - 1) {
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
    setStep(2)
    setSubPhase(inputLayout === 'folder' ? 'file-pairing' : 'pick-target')
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
        fileFormat,
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
        projectId: sourceCloudConfig.projectId,
        fileFormat,
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

  function handleSourceSelected(selection) {
    const parsed = parseSelection(selection)
    if (!parsed) return
    if (parsed.kind === 'cloud') {
      setSourceCloudConfig({
        provider: parsed.provider || 'google-cloud-storage',
        bucket: parsed.bucket || '',
        objectName: parsed.objectName || '',
        credentialsJson: parsed.credentialsJson || '',
        projectId: parsed.projectId || '',
      })
      setTargetCloudConfig(prev => ({
        ...prev,
        bucket: parsed.bucket || prev.bucket,
        credentialsJson: parsed.credentialsJson || prev.credentialsJson,
        projectId: parsed.projectId || prev.projectId,
      }))
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
      setTargetCloudConfig({
        provider: parsed.provider || 'google-cloud-storage',
        bucket: parsed.bucket || '',
        objectName: parsed.objectName || '',
        credentialsJson: parsed.credentialsJson || '',
        projectId: parsed.projectId || '',
      })
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
    setActiveUnitId(units[0]?.unitId || null)
    if (units[0]?.unitId) loadUnitConfig(units[0].unitId)
    setStep(3)
  }

  useEffect(() => {
    const hasSource = isBatchMode
      ? Boolean(activeUnit?.sourcePaths?.length)
      : isStorageSelectionComplete(sourceStorageType, sourcePath, sourceCloudConfig)
    const hasTarget = isBatchMode
      ? Boolean(activeUnit?.targetPaths?.length)
      : isStorageSelectionComplete(targetStorageType, targetPath, targetCloudConfig)
    if (step !== 3 || !hasSource || !hasTarget || fileFormat === 'fixed-width' || fileFormat === 'json') return

    const controller = new AbortController()

    async function loadColumnPreview() {
      setColumnPreviewLoading(true)
      setColumnPreviewError('')
      try {
        const res = await fetch(absoluteApiUrl('/api/v1/validate/local/columns'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify(
            isBatchMode && sourceStorageType === 'cloud' && activeUnit
              ? {
                  source_cloud: {
                    provider: 'google-cloud-storage',
                    bucket: sourceCloudConfig.bucket,
                    object_name: activeUnit.sourcePaths[0],
                    credentials_json: sourceCloudConfig.credentialsJson,
                    project_id: sourceCloudConfig.projectId || undefined,
                  },
                  target_cloud: {
                    provider: 'google-cloud-storage',
                    bucket: targetCloudConfig.bucket || sourceCloudConfig.bucket,
                    object_name: activeUnit.targetPaths[0],
                    credentials_json: targetCloudConfig.credentialsJson || sourceCloudConfig.credentialsJson,
                    project_id: targetCloudConfig.projectId || sourceCloudConfig.projectId || undefined,
                  },
                  uid_column: uidColumn.trim(),
                  delimiter: delimiter.trim() || 'auto',
                  has_header: hasHeader,
                }
              : {
                  source_path: effectiveSourcePath,
                  target_path: effectiveTargetPath,
                  uid_column: uidColumn.trim(),
                  delimiter: delimiter.trim() || 'auto',
                  has_header: hasHeader,
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
    fileFormat,
  ])

  useEffect(() => {
    const hasSource = isStorageSelectionComplete(sourceStorageType, sourcePath, sourceCloudConfig)
    const hasTarget = isStorageSelectionComplete(targetStorageType, targetPath, targetCloudConfig)
    if ((step !== 3 && step !== 4) || !hasSource || !hasTarget || fileFormat !== 'fixed-width') return

    const controller = new AbortController()
    const params = new URLSearchParams()
    if (sourceStorageType === 'local' && sourcePath.trim()) params.set('source_path', sourcePath.trim())
    if (targetStorageType === 'local' && targetPath.trim()) params.set('target_path', targetPath.trim())
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
  }, [step, sourceStorageType, targetStorageType, sourcePath, targetPath, fileFormat])

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
    footerTrailingRows,
    hasHeader,
    fileFormat,
  ])

  async function handleValidate() {
    setIsRunning(true); setPhase('running'); setResult(null); setBatchResult(null); setErrorMsg('')
    try {
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
              footerTrailingRows,
              columnMappings: toColumnMappingPayload(mappings),
            },
          } : {}),
        }
        const bodyPayload = buildBatchValidatePayload({
          fileFormat,
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
          validateHeaderFormats,
          validateFooters,
          footerTrailingRows,
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

      const sourcePayload = buildStoragePayload('source', sourceStorageType, sourcePath, sourceCloudConfig)
      const targetPayload = buildStoragePayload('target', targetStorageType, targetPath, targetCloudConfig)
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
        footer_trailing_rows: footerTrailingRows,
        has_header: hasHeader,
        file_format: 'csv'
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


  const showFormatSelect = step === 1 && subPhase === 'format-select'
  const showInputLayout = step === 2 && subPhase === 'input-layout'
  const showTypeSelect = step === 2 && subPhase === 'type-select'
  const showPickSource = step === 2 && (subPhase === 'pick-source' || subPhase === 'pick-source-folder' || subPhase === 'pick-source-multi')
  const showPickTarget = step === 2 && (subPhase === 'pick-target' || subPhase === 'pick-target-folder' || subPhase === 'pick-target-multi')
  const showFilePairing = step === 2 && subPhase === 'file-pairing'
  const showConfigure  = step === 3
  const showReview     = step === 4
  const allBatchUnitsConfigured = sequentialBatchMapping
    ? validationUnits.every(u => isUnitMappingConfigured(u.unitId))
    : true

  const isValidForRun  = isBatchMode
    ? validationUnits.length > 0 && allBatchUnitsConfigured && (fileFormat === 'json'
      ? true
      : fileFormat === 'fixed-width'
        ? fwColumns.length > 0 && !!fwJoinColumn
        : !!uidColumn.trim())
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
    : (isStorageSelectionComplete(sourceStorageType, sourcePath, sourceCloudConfig) && isStorageSelectionComplete(targetStorageType, targetPath, targetCloudConfig) && !!uidColumn.trim())
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
        <StepIndicator currentStep={step} />
      </div>

      {/* Step content */}
      <div style={{
        background: 'var(--surface-1)', border: '1px solid var(--border-1)',
        borderRadius: 12, padding: '24px 28px',
      }}>

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

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
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
        {showConfigure && (
          <>
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
                      Column mapping — file pair {activeUnitIndex + 1} of {validationUnits.length}
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
                  {validationUnits.map((unit, index) => {
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
                  Map columns for this pair, then continue to the next file. You can return to earlier pairs from the list above.
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
            ) : fileFormat === 'csv' ? (
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
                footerTrailingRows={footerTrailingRows}
                onFooterTrailingRowsChange={setFooterTrailingRows}
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
            <div style={{ marginTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <button
                type="button"
                onClick={handleConfigureBack}
                className="btn btn-ghost"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M9 6H3M5.5 3.5L3 6l2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                {sequentialBatchMapping && activeUnitIndex > 0 ? 'Previous pair' : 'Back'}
              </button>
              <button
                type="button"
                onClick={handleConfigureContinue}
                disabled={sequentialBatchMapping && !isCurrentPairMappingValid()}
                className="btn btn-primary"
              >
                {sequentialBatchMapping && activeUnitIndex >= 0 && activeUnitIndex < validationUnits.length - 1
                  ? `Save & next pair (${activeUnitIndex + 2} of ${validationUnits.length})`
                  : 'Review & run'}
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 6h6M6.5 3.5L9 6l-2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
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
            {fileFormat === 'csv' ? (
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

            {fileFormat === 'csv' && (
              <ResolvedDelimiterNotice
                requestedDelimiter={delimiter}
                resolvedDelimiter={columnPreview.delimiter}
              />
            )}

            {fileFormat === 'csv' && uidColumn.trim() && (
              <MappingColumnPreview
                uidColumn={uidColumn}
                hasHeader={hasHeader}
                mappings={mappings}
                sourceSamples={columnPreview.sourceSamples}
                targetSamples={columnPreview.targetSamples}
                sampleRowCount={columnPreview.sampleRowCount}
              />
            )}

            {fileFormat === 'csv' && (
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
    </div>
  )
}
