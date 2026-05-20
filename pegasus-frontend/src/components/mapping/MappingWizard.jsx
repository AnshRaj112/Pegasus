import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import StepIndicator    from './StepIndicator'
import Step1_DataSource from './Step1_DataSource'
import Step2_FilePicker from './Step2_FilePicker'
import Step3_Configure  from './Step3_Configure'
import ActionBar        from './ActionBar'
import ParallelValidationModal from '../ParallelValidationModal'
import { buildMappingRows, toColumnMappingPayload } from './columnMapping'
import { buildAnalyzePayload, formatCheckBySource } from './mappingAnalyze'
import { saveValidationDraft } from '../../api/validationHistory'


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

function normalizeResult(data) {
  if (!data || data.mismatch_samples?.length || !data.mismatch_sample_groups) return data
  const g = data.mismatch_sample_groups
  return { ...data, mismatch_samples: [...(g.missing_in_target ?? []), ...(g.extra_in_target ?? []), ...(g.value_mismatch ?? [])] }
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
    if (payload.status === 'failed') throw new Error(payload.error || 'Validation job failed')
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

function FixedWidthConfigurator({
  sourcePath,
  targetPath,
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
}) {
  return (
    <div style={{ animation: 'fade-in 0.25s ease' }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
          Step 2 of 3
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 6 }}>
          Configure Fixed-Width Date Validation
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)', maxWidth: 760 }}>
          Specify character positions (0-indexed) and date format per side. Formats can differ (e.g. source dd-mm-yyyy, target mm-dd-yyyy); rows match when the parsed calendar date is the same.
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

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Source Configuration */}
        <div style={{
          background: 'var(--surface-1)',
          border: '1px solid var(--border-1)',
          borderRadius: 12,
          padding: 20,
          boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
        }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)' }} />
            Source Date Layout
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
            Target Date Layout
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
  const [fileFormat, setFileFormat] = useState('csv')
  const [sourceDateStart, setSourceDateStart] = useState(0)
  const [sourceDateEnd, setSourceDateEnd] = useState(10)
  const [sourceDateFormat, setSourceDateFormat] = useState('%Y%m%d')
  const [targetDateStart, setTargetDateStart] = useState(0)
  const [targetDateEnd, setTargetDateEnd] = useState(10)
  const [targetDateFormat, setTargetDateFormat] = useState('%Y-%m-%d')
  const [mappings, setMappings]   = useState([])
  const [uidColumn, setUidColumn] = useState('id')
  const [delimiter, setDelimiter] = useState('auto')

  const [columnPreview, setColumnPreview] = useState({
    sourceColumns: [],
    targetColumns: [],
    compareColumns: [],
    autoMappings: [],
    unmatchedSourceColumns: [],
    unmatchedTargetColumns: [],
    delimiter: 'auto',
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

  useEffect(() => {
    if (!initialMappingData) return

    const { detail, preview, step: targetStep, error } = initialMappingData

    // Reset parent data so this effect only executes once upon loading
    onResetInitialData()

    // Initialize configuration states from detail
    // Initialize configuration states from detail
    setSourceStorageType('local')
    setTargetStorageType('local')
    setSourcePath(detail.source_path || detail.source_filename || '')
    setTargetPath(detail.target_path || detail.target_filename || '')
    setValidateHeaderFormats(detail.validate_header_formats || false)
    setValidateFooters(detail.validate_footers || false)
    setFooterTrailingRows(detail.footer_trailing_rows || 1)

    if (detail.delimiter === 'fixed-width') {
      setFileFormat('fixed-width')
      const saved = detail.column_mappings || []
      const getVal = (name) => saved.find(m => m.source_column === name)?.target_column || ''
      setSourceDateStart(Number(getVal('source_date_start')) || 0)
      setSourceDateEnd(Number(getVal('source_date_end')) || 10)
      setSourceDateFormat(getVal('source_date_format') || '%Y%m%d')
      setTargetDateStart(Number(getVal('target_date_start')) || 0)
      setTargetDateEnd(Number(getVal('target_date_end')) || 10)
      setTargetDateFormat(getVal('target_date_format') || '%Y-%m-%d')
    } else {
      setFileFormat('csv')
      setUidColumn(detail.uid_column || 'id')
      setDelimiter(detail.delimiter || 'auto')
    }

    // Load previews
    if (preview && detail.delimiter !== 'fixed-width') {
      setColumnPreview({
        sourceColumns: preview.source_columns || [],
        targetColumns: preview.target_columns || [],
        compareColumns: preview.compare_columns || [],
        autoMappings: preview.auto_mappings || [],
        unmatchedSourceColumns: preview.unmatched_source_columns || [],
        unmatchedTargetColumns: preview.unmatched_target_columns || [],
        delimiter: preview.delimiter || 'auto',
      })
      setColumnPreviewError('')
    } else if (error) {
      setColumnPreviewError(error)
    }

    // Populate customized mappings
    const savedMappings = detail.column_mappings || []
    if (detail.delimiter !== 'fixed-width') {
      const mappingRows = savedMappings.map((m, idx) => ({
        id: idx + 1,
        sourceColumn: m.source_column,
        targetColumn: m.target_column,
        isAuto: false,
      }))
      setMappings(mappingRows)
    }

    // Route step
    setStep(targetStep)
    if (targetStep === 2) {
      setSubPhase('pick-source')
    }
    if (error) {
      setAnalyzeError(error)
      setColumnPreviewError(error)
    }
  }, [initialMappingData, onResetInitialData])



  function handleDataSourceNext(srcType, tgtType) {
    setSourceStorageType(srcType); setTargetStorageType(tgtType); setStep(2); setSubPhase('pick-source')
  }
  function handleSourceSelected(path) { setSourcePath(path); setSubPhase('pick-target') }
  function handleTargetSelected(path) { setTargetPath(path); setStep(3); }

  useEffect(() => {
    if (step !== 2 || !sourcePath || !targetPath || fileFormat === 'fixed-width') return

    const controller = new AbortController()

    async function loadColumnPreview() {
      setColumnPreviewLoading(true)
      setColumnPreviewError('')
      try {
        const params = new URLSearchParams({
          source_path: sourcePath.trim(),
          target_path: targetPath.trim(),
          uid_column: uidColumn.trim(),
          delimiter: delimiter.trim() || 'auto',
        })
        const res = await fetch(absoluteApiUrl(`/api/v1/validate/local/columns?${params}`), {
          method: 'GET',
          signal: controller.signal,
        })
        const raw = await res.text()
        let data = {}
        if (raw) {
          try { data = JSON.parse(raw) } catch { throw new Error(raw.trim().slice(0, 500)) }
        }
        if (!res.ok) throw new Error(formatDetail(data.detail) || `${res.status} ${res.statusText}`)

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
        })
        setMappings(prev => buildMappingRows(compareColumns, targetColumns.filter(col => col !== uidColumn.trim()), prev, autoMappings))
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
          })
          setMappings([])
        }
      } finally {
        if (!controller.signal.aborted) setColumnPreviewLoading(false)
      }
    }

    loadColumnPreview()
    return () => controller.abort()
  }, [step, sourcePath, targetPath, uidColumn, delimiter])

  useEffect(() => {
    if (step !== 2 || !sourcePath || !targetPath || fileFormat === 'fixed-width') return
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
            sourcePath,
            targetPath,
            uidColumn,
            delimiter,
            mappings,
            validateHeaderFormats,
            validateFooters,
            footerTrailingRows,
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
    uidColumn,
    delimiter,
    mappings,
    validateHeaderFormats,
    validateFooters,
    footerTrailingRows,
  ])

  async function handleValidate() {
    setIsRunning(true); setPhase('running'); setResult(null); setErrorMsg(''); setStep(3)
    try {
      const bodyPayload = fileFormat === 'fixed-width' ? {
        source_path: sourcePath.trim(),
        target_path: targetPath.trim(),
        file_format: 'fixed-width',
        fixed_width_config: {
          source_date_start: sourceDateStart,
          source_date_end: sourceDateEnd,
          source_date_format: sourceDateFormat.trim(),
          target_date_start: targetDateStart,
          target_date_end: targetDateEnd,
          target_date_format: targetDateFormat.trim(),
        }
      } : {
        source_path: sourcePath.trim(),
        target_path: targetPath.trim(),
        uid_column: uidColumn.trim(),
        delimiter: delimiter.trim() || 'auto',
        column_mappings: toColumnMappingPayload(mappings),
        validate_header_formats: validateHeaderFormats,
        validate_footers: validateFooters,
        footer_trailing_rows: footerTrailingRows,
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
      setPhase('error'); setErrorMsg(err instanceof Error ? err.message : String(err))
    } finally { setIsRunning(false) }
  }

  async function handleSaveAsDraft() {
    setDraftSaveStatus('saving')
    setDraftSaveError('')
    try {
      const draftPayload = fileFormat === 'fixed-width' ? {
        sourcePath: sourcePath.trim(),
        targetPath: targetPath.trim(),
        uidColumn: 'date',
        delimiter: 'fixed-width',
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
        sourcePath: sourcePath.trim(),
        targetPath: targetPath.trim(),
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
  const showTypeSelect = step === 2 && subPhase === 'type-select'
  const showPickSource = step === 2 && subPhase === 'pick-source'
  const showPickTarget = step === 2 && subPhase === 'pick-target'
  const showConfigure  = step === 3
  const showReview     = step === 4
  const isValidForRun  = fileFormat === 'fixed-width'
    ? (!!sourcePath && !!targetPath && !!sourceDateFormat.trim() && !!targetDateFormat.trim())
    : (!!sourcePath && !!targetPath && !!uidColumn.trim())

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

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {/* CSV Option */}
              <button
                onClick={() => { setFileFormat('csv'); setStep(2); setSubPhase('type-select') }}
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
                onClick={() => { setFileFormat('fixed-width'); setStep(2); setSubPhase('type-select') }}
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
            </div>
          </div>
        )}

        {/* Step 1b: Select Storage */}
        {showTypeSelect && (
          <div>
            <button
              onClick={() => { setStep(1); setSubPhase('format-select') }}
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
            value={sourcePath}
            onSelect={handleSourceSelected}
            onBack={() => setSubPhase('type-select')}
            disabled={false}
          />
        )}

        {/* Step 1c */}
        {showPickTarget && (
          <Step2_FilePicker
            panelLabel="Target"
            value={targetPath}
            onSelect={handleTargetSelected}
            onBack={() => setSubPhase('pick-source')}
            disabled={false}
          />
        )}

        {/* Step 2: Configure */}
        {showConfigure && (
          <>
            {/* Format Selector Tabs */}
            <div style={{
              display: 'flex',
              background: 'var(--surface-2)',
              border: '1px solid var(--border-2)',
              padding: 4,
              borderRadius: 10,
              marginBottom: 20,
              gap: 4
            }}>
              {[
                { id: 'csv', label: 'CSV File Validation' },
                { id: 'fixed-width', label: 'Fixed-Width Date Validation' }
              ].map(opt => {
                const active = fileFormat === opt.id
                return (
                  <button
                    key={opt.id}
                    onClick={() => setFileFormat(opt.id)}
                    style={{
                      flex: 1,
                      height: 36,
                      borderRadius: 7,
                      border: 'none',
                      background: active ? 'var(--surface-1)' : 'transparent',
                      color: active ? 'var(--accent)' : 'var(--text-3)',
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                      boxShadow: active ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {opt.label}
                  </button>
                )
              })}
            </div>

            {fileFormat === 'csv' ? (
              <Step3_Configure
                sourcePath={sourcePath}
                targetPath={targetPath}
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
                sourcePath={sourcePath}
                targetPath={targetPath}
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
            <div style={{ marginTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                type="button"
                onClick={() => { setStep(2); setSubPhase('pick-target') }}
                className="btn btn-ghost"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M9 6H3M5.5 3.5L3 6l2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Back
              </button>
              <button
                type="button"
                onClick={() => setStep(4)}
                className="btn btn-primary"
              >
                Review & Save
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
                { label: 'Source file', value: sourcePath, accent: 'var(--accent)' },
                { label: 'Target file', value: targetPath, accent: 'var(--blue)' },
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

            {/* Config summary */}
            {fileFormat === 'csv' ? (
              <div style={{
                display: 'flex', gap: 16, padding: '10px 14px', borderRadius: 9,
                background: 'var(--surface-2)', border: '1px solid var(--border-1)',
                fontSize: 12, color: 'var(--text-3)', marginBottom: 12, flexWrap: 'wrap',
              }}>
                <span>UID: <strong style={{ color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace' }}>{uidColumn || '—'}</strong></span>
                <span>Delimiter: <strong style={{ color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace' }}>{delimiter}</strong></span>
                <span>Columns mapped: <strong style={{ color: 'var(--text-1)' }}>{mappings.filter(m => m.targetCol).length} / {mappings.length || '—'}</strong></span>
              </div>
            ) : (
              <div style={{
                display: 'flex', gap: 16, padding: '10px 14px', borderRadius: 9,
                background: 'var(--surface-2)', border: '1px solid var(--border-1)',
                fontSize: 12, color: 'var(--text-3)', marginBottom: 12, flexWrap: 'wrap',
              }}>
                <span>Format: <strong style={{ color: 'var(--text-1)' }}>Fixed-Width Date Validation</strong></span>
                <span>Source date slice: <strong style={{ color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace' }}>[{sourceDateStart}:{sourceDateEnd}] ({sourceDateFormat})</strong></span>
                <span>Target date slice: <strong style={{ color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace' }}>[{targetDateStart}:{targetDateEnd}] ({targetDateFormat})</strong></span>
              </div>
            )}

            {/* Delimiter field */}
            {fileFormat === 'csv' && (
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block' }}>
                  <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 5 }}>
                    CSV Delimiter
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                      type="text"
                      value={delimiter}
                      onChange={e => setDelimiter(e.target.value)}
                      placeholder="auto"
                      className="input input-mono"
                      style={{ maxWidth: 160 }}
                    />
                    <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
                      Supports <code style={{ fontFamily: 'Geist Mono, monospace', fontSize: 11 }}>tab</code>, <code style={{ fontFamily: 'Geist Mono, monospace', fontSize: 11 }}>|</code>, <code style={{ fontFamily: 'Geist Mono, monospace', fontSize: 11 }}>::</code>
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
                  <StatCard label="Source rows" value={result.summary?.source_row_count ?? '—'} />
                  <StatCard label="Target rows" value={result.summary?.target_row_count ?? '—'} />
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
