import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Input, Modal, Select, Space, Table, Tag, Typography } from 'antd'
import {
  basename,
  fetchValidationHistory,
  fetchValidationHistoryDetail,
  fetchValidationHistoryMismatches,
  formatDuration,
  deleteValidationHistoryRun,
  deleteValidationHistoryByPair,
  deleteValidationHistoryAll,
  fetchLocalColumnPreview,
} from '../api/validationHistory'

const HISTORY_MISMATCH_PAGE_SIZE = 5000
const HISTORY_PAGE_SIZE = 15
const HISTORY_PAGE_SIZE_OPTIONS = [15, 25, 50, 100]
const HISTORY_FETCH_BATCH_SIZE = 100

const TrashIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6h18"/>
    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
    <line x1="10" x2="10" y1="11" y2="17"/>
    <line x1="14" x2="14" y1="11" y2="17"/>
  </svg>
)

function DeleteButton({ onClick, title }) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      title={title}
      style={{
        background: hovered ? 'var(--danger-muted)' : 'transparent',
        border: 'none',
        color: hovered ? 'var(--danger)' : 'var(--text-3)',
        cursor: 'pointer',
        padding: '6px',
        borderRadius: '6px',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all 0.15s ease',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <TrashIcon />
    </button>
  )
}

function ConfirmationModal({ isOpen, title, message, onConfirm, onCancel }) {
  if (!isOpen) return null
  return (
    <Modal open centered onCancel={onCancel} onOk={onConfirm} okText="Delete" okButtonProps={{ danger: true }} cancelText="Cancel" title={title}>
      <Typography.Paragraph style={{ marginBottom: 0 }}>{message}</Typography.Paragraph>
    </Modal>
  )
}

function TabButton({ active, onClick, children }) {
  return (
    <Button type={active ? 'primary' : 'default'} onClick={onClick} style={{ borderRadius: 12 }}>
      {children}
    </Button>
  )
}

function Panel({ children, style }) {
  return (
    <div style={{ padding: 18, borderRadius: 12, background: 'var(--surface-1)', border: '1px solid var(--border-1)', ...style }}>
      {children}
    </div>
  )
}

function PaginationControls({
  page,
  pageCount,
  totalItems,
  pageSize,
  onPrevious,
  onNext,
  onPageChange,
  onPageSizeChange,
  label,
}) {
  if (!totalItems) return null

  const startItem = (page - 1) * pageSize + 1
  const endItem = Math.min(page * pageSize, totalItems)

  return (
    <div
      style={{
        marginTop: 14,
        paddingTop: 12,
        borderTop: '1px solid var(--border-1)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        flexWrap: 'wrap',
      }}
    >
      <p style={{ margin: 0, fontSize: 12, color: 'var(--text-3)' }}>
        Showing {startItem}-{endItem} of {totalItems} {label}
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button onClick={onPrevious} disabled={page <= 1}>Previous</Button>
          <Typography.Text style={{ fontSize: 12, color: 'var(--text-3)' }}>
            Page {page} of {pageCount}
          </Typography.Text>
          <Button onClick={onNext} disabled={page >= pageCount}>Next</Button>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-3)' }}>
          Go to
          <input
            type="number"
            min="1"
            max={pageCount}
            value={page}
            onChange={(e) => {
              const nextPage = Number.parseInt(e.target.value, 10)
              if (!Number.isNaN(nextPage)) {
                onPageChange(Math.min(Math.max(1, nextPage), pageCount))
              }
            }}
            style={{ width: 72, padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border-1)' }}
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-3)' }}>
          Rows
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border-1)' }}
          >
            {HISTORY_PAGE_SIZE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  )
}

function FileDetailTile({ label, value }) {
  return (
    <Card size="small" style={{ borderRadius: 16, background: 'rgba(255,255,255,0.7)' }} styles={{ body: { padding: 12 } }}>
      <Typography.Text style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748B' }}>{label}</Typography.Text>
      <Typography.Paragraph style={{ marginBottom: 0, marginTop: 8, wordBreak: 'break-word', fontWeight: 500, color: '#0F172A' }}>{value || '—'}</Typography.Paragraph>
    </Card>
  )
}

function parseHistoryRowDetail(rowDetail) {
  if (!rowDetail) return null
  if (typeof rowDetail === 'object') return rowDetail
  if (typeof rowDetail !== 'string') return null

  const trimmed = rowDetail.trim()
  if (!trimmed || trimmed === '{}') return null

  try {
    return JSON.parse(trimmed)
  } catch {
    return null
  }
}

function normalizeHistoryMismatchRow(row) {
  return {
    ...row,
    row_detail: parseHistoryRowDetail(row.row_detail),
  }
}

function buildHistoryReportResult(detail, mismatches) {
  const items = (mismatches?.items ?? []).map(normalizeHistoryMismatchRow)
  const mismatchCounts = detail?.mismatch_counts ?? {
    missing_in_target: 0,
    extra_in_target: 0,
    value_mismatch: 0,
  }
  const totalMismatchRecords =
    Number(mismatchCounts.missing_in_target ?? 0) +
    Number(mismatchCounts.extra_in_target ?? 0) +
    Number(mismatchCounts.value_mismatch ?? 0)

  const groupedItems = {
    missing_in_target: [],
    extra_in_target: [],
    value_mismatch: [],
  }

  for (const item of items) {
    if (groupedItems[item.mismatch_type]) {
      groupedItems[item.mismatch_type].push(item)
    }
  }

  return {
    ...detail,
    run_id: detail?.run_id,
    summary: {
      is_match: detail?.is_match,
      source_row_count: detail?.source_row_count,
      target_row_count: detail?.target_row_count,
      total_mismatch_records: totalMismatchRecords,
    },
    mismatch_counts: mismatchCounts,
    mismatch_samples: items,
    mismatch_sample_groups: groupedItems,
  }
}

async function fetchAllHistoryMismatches(runId) {
  const items = []
  let offset = 0
  let total = 0

  while (true) {
    const page = await fetchValidationHistoryMismatches(runId, {
      limit: HISTORY_MISMATCH_PAGE_SIZE,
      offset,
    })
    const pageItems = Array.isArray(page.items) ? page.items : []
    total = page.total ?? total
    items.push(...pageItems)
    offset += pageItems.length

    if (!pageItems.length || offset >= total) break
  }

  return { run_id: runId, items, total, offset: 0, limit: HISTORY_MISMATCH_PAGE_SIZE }
}

async function fetchAllValidationHistoryRows({ sourcePath, targetPath } = {}) {
  const items = []
  let offset = 0
  let total = 0

  while (true) {
    const page = await fetchValidationHistory({
      limit: HISTORY_FETCH_BATCH_SIZE,
      offset,
      sourcePath,
      targetPath,
    })
    const pageItems = Array.isArray(page.items) ? page.items : []
    total = page.total ?? total
    items.push(...pageItems)
    offset += pageItems.length

    if (!pageItems.length || offset >= total) break
  }

  return { items, total }
}

function hasHistoryFilePaths(detail) {
  const source = (detail.source_path || detail.source_filename || '').trim()
  const target = (detail.target_path || detail.target_filename || '').trim()
  return Boolean(source && target)
}

function hasSavedMappingConfig(detail) {
  if (detail.delimiter === 'fixed-width' || detail.delimiter === 'fixed') {
    return true
  }
  const mappings = detail.column_mappings || []
  const compared = detail.compared_columns || []
  return mappings.length > 0 || compared.length > 0
}

function columnStructureWarning(detail, preview) {
  if (!preview) return ''

  const savedUid = (detail.uid_column || 'id').trim()
  const savedMappings = detail.column_mappings || []
  const savedComparedCols = detail.compared_columns || []

  if (!preview.source_columns.includes(savedUid) || !preview.target_columns.includes(savedUid)) {
    return 'The join key column changed in one or both files since this mapping was saved.'
  }

  for (const m of savedMappings) {
    if (!preview.source_columns.includes(m.source_column) || !preview.target_columns.includes(m.target_column)) {
      return 'One or more mapped columns are missing from the current files.'
    }
  }

  const targetColsMapped = preview.target_columns.map(col => {
    const m = savedMappings.find(sm => sm.target_column === col)
    return m ? m.source_column : col
  })
  const currentCompareCols = preview.source_columns.filter(col => {
    if (col === savedUid) return false
    return targetColsMapped.includes(col)
  })
  const sortedCurrent = [...currentCompareCols].sort()
  const sortedSaved = [...savedComparedCols].sort()
  const listsEqual = sortedCurrent.length === sortedSaved.length
    && sortedCurrent.every((val, index) => val === sortedSaved[index])
  if (!listsEqual) {
    return 'Compared columns differ from the saved mapping; review mappings before validating.'
  }

  return ''
}

function resolveMappingHistoryResume(detail, preview, previewError) {
  if (!hasHistoryFilePaths(detail)) {
    return {
      step: 1,
      error: previewError
        ? `Underlying files could not be accessed: ${previewError}. Please select the files to edit the saved paths.`
        : 'Saved file paths are missing. Please select the source and target files.',
    }
  }

  if (!hasSavedMappingConfig(detail)) {
    return {
      step: 3,
      error: previewError || 'No saved column mappings found for this file pair. Configure mappings to continue.',
    }
  }

  const warnings = [
    previewError ? `Could not refresh file headers: ${previewError}. Saved mappings are loaded; re-select files if validation fails.` : '',
    columnStructureWarning(detail, preview),
  ].filter(Boolean)

  return {
    step: 4,
    error: warnings.join(' '),
  }
}

function StatusBadge({ isMatch, status }) {
  if (status && status !== 'completed') {
    return (
      <Tag>{status}</Tag>
    )
  }
  return (
    <Tag color={isMatch ? 'green' : 'red'}>{isMatch ? 'Match' : 'Mismatches'}</Tag>
  )
}

function RunDetailPanel({ runId, onClose }) {
  const [detail, setDetail] = useState(null)
  const [mismatches, setMismatches] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    Promise.all([
      fetchValidationHistoryDetail(runId),
      fetchValidationHistoryMismatches(runId, { limit: 50 }),
    ])
      .then(([d, m]) => {
        if (!cancelled) {
          setDetail(d)
          setMismatches(m)
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [runId])

  if (loading) return <p style={{ color: 'var(--text-3)', fontSize: 13 }}>Loading run details…</p>
  if (error) return <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p>
  if (!detail) return null

  const counts = detail.mismatch_counts || {}
  const durations = detail.durations || {}

  return (
    <Panel style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <h4 style={{ margin: '0 0 8px', fontSize: 15, color: 'var(--text-1)' }}>Validation report</h4>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-3)' }}>
            {basename(detail.source_path || detail.source_filename)} → {basename(detail.target_path || detail.target_filename)}
          </p>
        </div>
        <Button onClick={onClose}>Close</Button>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 12, fontSize: 13 }}>
        <span>Upload: <strong>{formatDuration(durations.upload_seconds)}</strong></span>
        <span>Validation: <strong>{formatDuration(durations.validation_seconds)}</strong></span>
        <span>Total: <strong>{formatDuration(durations.total_seconds)}</strong></span>
        <span>Missing: <strong>{counts.missing_in_target ?? 0}</strong></span>
        <span>Extra: <strong>{counts.extra_in_target ?? 0}</strong></span>
        <span>Value: <strong>{counts.value_mismatch ?? 0}</strong></span>
      </div>

      <h5 style={{ margin: '16px 0 8px', fontSize: 13, color: 'var(--text-2)' }}>Column mapping ({detail.column_mappings?.length ?? 0})</h5>
      {detail.column_mappings?.length ? (
        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--text-3)' }}>
              <th style={{ padding: '4px 8px' }}>Source</th>
              <th style={{ padding: '4px 8px' }}>Target</th>
            </tr>
          </thead>
          <tbody>
            {detail.column_mappings.map((m) => (
              <tr key={`${m.source_column}-${m.target_column}`} style={{ borderTop: '1px solid var(--border-1)' }}>
                <td style={{ padding: '6px 8px' }}>{m.source_column}</td>
                <td style={{ padding: '6px 8px' }}>{m.target_column}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--text-4)' }}>No explicit mappings (headers matched by name).</p>
      )}

      {mismatches?.items?.length ? (
        <>
          <h5 style={{ margin: '16px 0 8px', fontSize: 13, color: 'var(--text-2)' }}>
            Sample mismatches ({mismatches.items.length} of {mismatches.total})
          </h5>
          <div style={{ maxHeight: 220, overflow: 'auto', fontSize: 11, fontFamily: 'monospace' }}>
            {mismatches.items.map((row, i) => (
              <div key={`${row.uid}-${row.mismatch_type}-${i}`} style={{ padding: '4px 0', borderBottom: '1px solid var(--border-1)' }}>
                {row.mismatch_type} · {row.uid}
                {row.column_name ? ` · ${row.column_name}` : ''}
              </div>
            ))}
          </div>
        </>
      ) : null}
    </Panel>
  )
}

export default function History({ onLoadMapping }) {
  const navigate = useNavigate()
  const [topTab, setTopTab] = useState('mapping')
  const [pairFilter, setPairFilter] = useState({ source: '', target: '' })
  const [mappingRows, setMappingRows] = useState([])
  const [mappingLoading, setMappingLoading] = useState(false)
  const [mappingPage, setMappingPage] = useState(1)
  const [mappingPageSize, setMappingPageSize] = useState(HISTORY_PAGE_SIZE)
  const [validationRows, setValidationRows] = useState([])
  const [validationTotal, setValidationTotal] = useState(0)
  const [validationPage, setValidationPage] = useState(1)
  const [validationPageSize, setValidationPageSize] = useState(HISTORY_PAGE_SIZE)
  const [validationLoading, setValidationLoading] = useState(false)
  const [loadingMappingId, setLoadingMappingId] = useState(null)
  const [error, setError] = useState('')
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [openingRunId, setOpeningRunId] = useState(null)

  const [confirmState, setConfirmState] = useState({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: null,
  })

  const handleOpenValidationReport = async (row) => {
    setError('')
    setOpeningRunId(row.run_id)
    setSelectedRunId(null)

    try {
      const [detail, mismatches] = await Promise.all([
        fetchValidationHistoryDetail(row.run_id),
        fetchAllHistoryMismatches(row.run_id),
      ])
      navigate('/report', { state: { result: buildHistoryReportResult(detail, mismatches) } })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setOpeningRunId(null)
    }
  }

  const handleMappingClick = async (row) => {
    setError('')
    setLoadingMappingId(row.run_id)
    try {
      // 1. Fetch the full detail of this saved validation run/mapping draft
      const detail = await fetchValidationHistoryDetail(row.run_id)

      // Fixed-width runs skip CSV header preview; resume at review when paths exist.
      if (detail.delimiter === 'fixed-width' || detail.delimiter === 'fixed') {
        const { step, error } = resolveMappingHistoryResume(detail, null, '')
        onLoadMapping({ detail, preview: null, step, error })
        return
      }

      // Refresh headers when possible; routing uses saved mappings, not preview success.
      let preview = null
      let previewError = ''
      try {
        preview = await fetchLocalColumnPreview({
          sourcePath: detail.source_path || detail.source_filename || '',
          targetPath: detail.target_path || detail.target_filename || '',
          uidColumn: detail.uid_column || 'id',
          delimiter: detail.delimiter || 'auto',
        })
      } catch (err) {
        previewError = err instanceof Error ? err.message : String(err)
      }

      const { step, error } = resolveMappingHistoryResume(detail, preview, previewError)
      onLoadMapping({ detail, preview, step, error })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoadingMappingId(null)
    }
  }


  const handleDeleteMapping = (row) => {
    const srcName = basename(row.source_path || row.source_filename)
    const tgtName = basename(row.target_path || row.target_filename)
    setConfirmState({
      isOpen: true,
      title: 'Delete Mapping History',
      message: `Are you sure you want to permanently delete the saved mapping history and all validation runs for ${srcName} ↔ ${tgtName}? This cannot be undone.`,
      onConfirm: async () => {
        try {
          await deleteValidationHistoryByPair(
            row.source_path || row.source_filename,
            row.target_path || row.target_filename
          )
          setMappingRows((prev) =>
            prev.filter(
              (item) =>
                !(
                  (item.source_path === row.source_path || item.source_filename === row.source_filename) &&
                  (item.target_path === row.target_path || item.target_filename === row.target_filename)
                )
            )
          )
          setValidationRows((prev) =>
            prev.filter(
              (item) =>
                !(
                  (item.source_path === row.source_path || item.source_filename === row.source_filename) &&
                  (item.target_path === row.target_path || item.target_filename === row.target_filename)
                )
            )
          )
          if (selectedRunId === row.run_id) setSelectedRunId(null)
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e))
        } finally {
          setConfirmState((prev) => ({ ...prev, isOpen: false }))
        }
      },
    })
  }

  const handleDeleteRun = (row) => {
    const dateStr = row.completed_at
      ? new Date(row.completed_at).toLocaleString()
      : new Date(row.created_at).toLocaleString()
    setConfirmState({
      isOpen: true,
      title: 'Delete Validation Run',
      message: `Are you sure you want to permanently delete the validation run from ${dateStr}? This will also delete all associated mismatch records and report data.`,
      onConfirm: async () => {
        try {
          await deleteValidationHistoryRun(row.run_id)
          setMappingRows((prev) => prev.filter((item) => item.run_id !== row.run_id))
          setValidationRows((prev) => prev.filter((item) => item.run_id !== row.run_id))
          setValidationTotal((prev) => Math.max(0, prev - 1))
          if (selectedRunId === row.run_id) setSelectedRunId(null)
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e))
        } finally {
          setConfirmState((prev) => ({ ...prev, isOpen: false }))
        }
      },
    })
  }

  const handleClearAll = (tabName) => {
    const isMapping = tabName === 'mapping'
    setConfirmState({
      isOpen: true,
      title: isMapping ? 'Clear All Mapping History?' : 'Clear All Validation History?',
      message: `Are you sure you want to permanently delete all historical runs and saved mappings? This action will completely empty your validation database. This cannot be undone.`,
      onConfirm: async () => {
        try {
          await deleteValidationHistoryAll()
          setMappingRows([])
          setValidationRows([])
          setValidationTotal(0)
          setMappingPage(1)
          setValidationPage(1)
          setSelectedRunId(null)
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e))
        } finally {
          setConfirmState((prev) => ({ ...prev, isOpen: false }))
        }
      },
    })
  }


  const loadMappingHistory = useCallback(async () => {
    setMappingLoading(true)
    setError('')
    try {
      const data = await fetchAllValidationHistoryRows()
      setMappingRows(Array.isArray(data.items) ? data.items : [])
    } catch (e) {
      setMappingRows([])
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setMappingLoading(false)
    }
  }, [])

  const loadValidationHistory = useCallback(async (page, pageSize) => {
    setValidationLoading(true)
    setError('')
    try {
      const data = await fetchValidationHistory({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        sourcePath: pairFilter.source.trim() || undefined,
        targetPath: pairFilter.target.trim() || undefined,
      })
      setValidationRows(Array.isArray(data.items) ? data.items : [])
      setValidationTotal(data.total ?? 0)
    } catch (e) {
      setValidationRows([])
      setValidationTotal(0)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setValidationLoading(false)
    }
  }, [pairFilter.source, pairFilter.target])

  useEffect(() => {
    if (topTab === 'mapping') {
      loadMappingHistory()
    }
  }, [topTab, loadMappingHistory])

  useEffect(() => {
    if (topTab === 'validation') {
      loadValidationHistory(validationPage, validationPageSize)
    }
  }, [topTab, validationPage, validationPageSize, loadValidationHistory])

  const mappingPairs = useMemo(() => {
    const seen = new Map()
    for (const row of mappingRows) {
      const key = `${row.source_path || row.source_filename}|${row.target_path || row.target_filename}`
      if (!seen.has(key)) seen.set(key, row)
    }
    return [...seen.values()]
  }, [mappingRows])

  const mappingPageCount = Math.max(1, Math.ceil(mappingPairs.length / mappingPageSize))
  const validationPageCount = Math.max(1, Math.ceil(validationTotal / validationPageSize))
  const safeMappingPage = Math.min(mappingPage, mappingPageCount)
  const safeValidationPage = Math.min(validationPage, validationPageCount)
  const paginatedMappingPairs = useMemo(() => {
    const start = (safeMappingPage - 1) * mappingPageSize
    return mappingPairs.slice(start, start + mappingPageSize)
  }, [mappingPairs, mappingPageSize, safeMappingPage])

  useEffect(() => {
    if (mappingPage !== safeMappingPage) setMappingPage(safeMappingPage)
  }, [mappingPage, safeMappingPage])

  useEffect(() => {
    if (validationPage !== safeValidationPage) setValidationPage(safeValidationPage)
  }, [validationPage, safeValidationPage])

  const handleApplyValidationFilter = () => {
    setValidationPage(1)
  }

  const handlePreviousMappingPage = () => setMappingPage((page) => Math.max(1, page - 1))
  const handleNextMappingPage = () => setMappingPage((page) => Math.min(mappingPageCount, page + 1))
  const handlePreviousValidationPage = () => setValidationPage((page) => Math.max(1, page - 1))
  const handleNextValidationPage = () => setValidationPage((page) => Math.min(validationPageCount, page + 1))
  const handleMappingPageChange = (nextPage) => setMappingPage(Math.min(Math.max(1, nextPage), mappingPageCount))
  const handleValidationPageChange = (nextPage) => setValidationPage(Math.min(Math.max(1, nextPage), validationPageCount))
  const handleMappingPageSizeChange = (nextPageSize) => {
    setMappingPageSize(nextPageSize)
    setMappingPage(1)
  }
  const handleValidationPageSizeChange = (nextPageSize) => {
    setValidationPageSize(nextPageSize)
    setValidationPage(1)
  }

  return (
    <div style={{ padding: 12 }}>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <TabButton active={topTab === 'mapping'} onClick={() => setTopTab('mapping')}>Mapping History</TabButton>
        <TabButton active={topTab === 'validation'} onClick={() => setTopTab('validation')}>Validation History</TabButton>
      </div>

      {topTab === 'mapping' ? (
        <Panel>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, borderBottom: '1px solid var(--border-1)', paddingBottom: 12 }}>
            <div>
              <h4 style={{ margin: '0 0 4px', fontSize: 15, color: 'var(--text-1)', fontWeight: 600 }}>Saved mappings by file pair</h4>
              <p style={{ margin: 0, fontSize: 13, color: 'var(--text-3)' }}>
                Latest validation run per source/target pair, including column mappings used.
              </p>
            </div>
            {mappingPairs.length ? (
              <Button danger onClick={() => handleClearAll('mapping')}>Clear all mappings</Button>
            ) : null}
          </div>
          {error ? <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p> : null}
          {mappingLoading ? <p style={{ color: 'var(--text-4)' }}>Loading…</p> : null}
          {!mappingLoading && !mappingPairs.length ? (
            <p style={{ color: 'var(--text-4)', marginBottom: 0 }}>No mapping history yet. Run a validation with persistence enabled.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {paginatedMappingPairs.map((row) => (
                <Card
                  key={row.run_id}
                  hoverable={!loadingMappingId}
                  onClick={() => handleMappingClick(row)}
                  style={{ opacity: loadingMappingId === row.run_id ? 0.7 : 1, cursor: loadingMappingId ? 'wait' : 'pointer' }}
                  styles={{ body: { padding: 16 } }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                    <span style={{ fontSize: 13, color: 'var(--text-1)', fontWeight: 500 }}>
                      Mapping pair
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      {loadingMappingId === row.run_id ? <Typography.Text type="secondary">Loading…</Typography.Text> : <StatusBadge isMatch={row.is_match} status={row.status} />}
                      <DeleteButton title="Delete mapping history" onClick={() => handleDeleteMapping(row)} />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
                    <FileDetailTile label="Source file name" value={basename(row.source_path || row.source_filename)} />
                    <FileDetailTile label="Source file path" value={row.source_path || row.source_filename} />
                    <FileDetailTile label="Target file name" value={basename(row.target_path || row.target_filename)} />
                    <FileDetailTile label="Target file path" value={row.target_path || row.target_filename} />
                  </div>
                  <Typography.Paragraph style={{ margin: '10px 0 0', fontSize: 12, color: 'var(--text-3)' }}>
                    {row.delimiter === 'fixed-width' || row.delimiter === 'fixed' ? (
                      <Typography.Text style={{ color: 'var(--blue, #3b82f6)', fontWeight: 500 }}>Fixed-Width Date validation</Typography.Text>
                    ) : (
                      <>
                        {row.mapping_count} mapping(s) · UID <code>{row.uid_column}</code>
                      </>
                    )}
                  </Typography.Paragraph>
                </Card>
              ))}
            </div>
          )}
          <PaginationControls
            page={safeMappingPage}
            pageCount={mappingPageCount}
            totalItems={mappingPairs.length}
            pageSize={mappingPageSize}
            onPrevious={handlePreviousMappingPage}
            onNext={handleNextMappingPage}
            onPageChange={handleMappingPageChange}
            onPageSizeChange={handleMappingPageSizeChange}
            label="mapping groups"
          />
        </Panel>
      ) : (
        <Panel>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, borderBottom: '1px solid var(--border-1)', paddingBottom: 12 }}>
            <div>
              <h4 style={{ margin: '0 0 4px', fontSize: 15, color: 'var(--text-1)', fontWeight: 600 }}>Validation History Logs</h4>
              <p style={{ margin: 0, fontSize: 13, color: 'var(--text-3)' }}>
                All historical validation run logs and mismatch summaries.
              </p>
            </div>
            {validationRows.length ? (
              <Button danger onClick={() => handleClearAll('validation')}>Clear all history</Button>
            ) : null}
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12, alignItems: 'flex-end' }}>
            <label style={{ fontSize: 12, color: 'var(--text-3)' }}>
              Source path
              <Input
                type="text"
                value={pairFilter.source}
                onChange={(e) => setPairFilter((p) => ({ ...p, source: e.target.value }))}
                placeholder="/path/to/source.csv"
                style={{ display: 'block', marginTop: 4, minWidth: 220 }}
              />
            </label>
            <label style={{ fontSize: 12, color: 'var(--text-3)' }}>
              Target path
              <Input
                type="text"
                value={pairFilter.target}
                onChange={(e) => setPairFilter((p) => ({ ...p, target: e.target.value }))}
                placeholder="/path/to/target.csv"
                style={{ display: 'block', marginTop: 4, minWidth: 220 }}
              />
            </label>
            <Button onClick={handleApplyValidationFilter} disabled={validationLoading}>
              {validationLoading ? 'Loading…' : 'Apply filter'}
            </Button>
          </div>

          {error ? <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p> : null}

          {!validationLoading && !validationRows.length && !error ? (
            <p style={{ color: 'var(--text-4)', marginBottom: 0 }}>No validations recorded yet.</p>
          ) : null}

          {validationRows.length ? (
            <div style={{ overflowX: 'auto' }}>
              <Table
                rowKey="run_id"
                pagination={false}
                dataSource={validationRows}
                columns={[
                  { title: 'When', dataIndex: 'created_at', render: (_, row) => row.completed_at ? new Date(row.completed_at).toLocaleString() : new Date(row.created_at).toLocaleString() },
                  { title: 'Source file', render: (_, row) => <div><div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-1)' }}>{basename(row.source_path || row.source_filename)}</div><div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-2)', wordBreak: 'break-word' }}>{row.source_path || row.source_filename}</div></div> },
                  { title: 'Target file', render: (_, row) => <div><div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-1)' }}>{basename(row.target_path || row.target_filename)}</div><div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-2)', wordBreak: 'break-word' }}>{row.target_path || row.target_filename}</div>{(row.delimiter === 'fixed-width' || row.delimiter === 'fixed') && <div style={{ fontSize: 10, color: 'var(--blue, #3b82f6)', fontWeight: 600, marginTop: 2 }}>Fixed-Width Format</div>}</div> },
                  { title: 'Mappings', render: (_, row) => row.delimiter === 'fixed-width' || row.delimiter === 'fixed' ? 'Date slice' : row.mapping_count },
                  { title: 'Duration', render: (_, row) => formatDuration(row.durations?.validation_seconds ?? row.durations?.total_seconds) },
                  { title: 'Result', render: (_, row) => <StatusBadge isMatch={row.is_match} status={row.status} /> },
                  { title: 'Actions', align: 'right', render: (_, row) => <Space><Button onClick={(e) => { e.stopPropagation(); handleOpenValidationReport(row) }} disabled={openingRunId === row.run_id}>View report</Button><DeleteButton title="Delete validation run" onClick={() => handleDeleteRun(row)} /></Space> },
                ]}
                onRow={(row) => ({
                  onClick: () => handleOpenValidationReport(row),
                  style: { cursor: openingRunId === row.run_id ? 'wait' : 'pointer' },
                })}
              />
              <PaginationControls
                page={safeValidationPage}
                pageCount={validationPageCount}
                totalItems={validationTotal}
                pageSize={validationPageSize}
                onPrevious={handlePreviousValidationPage}
                onNext={handleNextValidationPage}
                onPageChange={handleValidationPageChange}
                onPageSizeChange={handleValidationPageSizeChange}
                label="validation runs"
              />
            </div>
          ) : null}

          {selectedRunId ? (
            <RunDetailPanel runId={selectedRunId} onClose={() => setSelectedRunId(null)} />
          ) : null}
        </Panel>
      )}
      <ConfirmationModal
        isOpen={confirmState.isOpen}
        title={confirmState.title}
        message={confirmState.message}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState((prev) => ({ ...prev, isOpen: false }))}
      />
    </div>
  )
}