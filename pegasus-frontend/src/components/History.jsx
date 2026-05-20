import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.3)',
      backdropFilter: 'blur(3px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      animation: 'fade-in 0.12s ease-out',
    }}>
      <div style={{
        background: 'var(--surface-3)',
        border: '1px solid var(--border-1)',
        borderRadius: '12px',
        padding: '20px',
        maxWidth: '400px',
        width: '90%',
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.08)',
      }}>
        <h4 style={{ margin: '0 0 8px', fontSize: '15px', color: 'var(--text-1)', fontWeight: 600 }}>{title}</h4>
        <p style={{ margin: '0 0 20px', fontSize: '13px', color: 'var(--text-2)', lineHeight: '1.5' }}>{message}</p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button type="button" className="btn" style={{ background: 'var(--danger)', color: '#fff', fontWeight: 600 }} onClick={onConfirm}>Delete</button>
        </div>
      </div>
    </div>
  )
}

function TabButton({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={active ? 'px-4 py-2 rounded-xl bg-slate-900 text-white' : 'px-4 py-2 rounded-xl bg-white border'}
      style={{ border: '1px solid var(--border-1)', cursor: 'pointer' }}
    >
      {children}
    </button>
  )
}

function Panel({ children, style }) {
  return (
    <div style={{ padding: 18, borderRadius: 12, background: 'var(--surface-1)', border: '1px solid var(--border-1)', ...style }}>
      {children}
    </div>
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

function StatusBadge({ isMatch, status }) {
  if (status && status !== 'completed') {
    return (
      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: 'var(--surface-3)', color: 'var(--text-3)' }}>
        {status}
      </span>
    )
  }
  return (
    <span
      style={{
        fontSize: 11,
        padding: '2px 8px',
        borderRadius: 999,
        background: isMatch ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.12)',
        color: isMatch ? 'var(--success)' : 'var(--danger)',
      }}
    >
      {isMatch ? 'Match' : 'Mismatches'}
    </span>
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
        <button type="button" className="btn btn-secondary" onClick={onClose}>Close</button>
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
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
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

      // 2. If it's a fixed-width run, bypass CSV column headers preview
      if (detail.delimiter === 'fixed-width' || detail.delimiter === 'fixed') {
        onLoadMapping({
          detail,
          preview: null,
          step: 3,
          error: '',
        })
        return
      }

      // Fetch the current column headers from the server-local files
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

      // If we couldn't load the column headers, fallback to Step 1 (Select Files) so paths can be corrected
      if (!preview) {
        onLoadMapping({
          detail,
          preview: null,
          step: 1,
          error: `Underlying files could not be accessed: ${previewError}. Please select the files to edit the saved paths.`,
        })
        return
      }

      // 3. Perform a robust check to see if the file headers or compared columns have changed
      const savedUid = (detail.uid_column || 'id').trim()
      const savedMappings = detail.column_mappings || []
      const savedComparedCols = detail.compared_columns || []
      let match = true

      // A. Verify UID exists in both files
      if (!preview.source_columns.includes(savedUid) || !preview.target_columns.includes(savedUid)) {
        match = false
      }

      // B. Verify that all configured mappings point to columns that actually exist
      if (match) {
        for (const m of savedMappings) {
          if (!preview.source_columns.includes(m.source_column) || !preview.target_columns.includes(m.target_column)) {
            match = false
            break
          }
        }
      }

      // C. Reconstruct compared columns and verify they match exactly
      if (match) {
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
        const listsEqual = sortedCurrent.length === sortedSaved.length &&
          sortedCurrent.every((val, index) => val === sortedSaved[index])

        if (!listsEqual) {
          match = false
        }
      }

      // 4. Step 3 = configure mapping; step 4 = review & run when saved mapping still matches files
      const targetStep = match ? 4 : 3
      onLoadMapping({
        detail,
        preview,
        step: targetStep,
        error: match ? '' : 'Underlying file structure or columns have changed since this mapping was saved. Please configure mappings again.',
      })
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
          setItems((prev) =>
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
          setItems((prev) => prev.filter((item) => item.run_id !== row.run_id))
          setTotal((prev) => Math.max(0, prev - 1))
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
          setItems([])
          setTotal(0)
          setSelectedRunId(null)
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e))
        } finally {
          setConfirmState((prev) => ({ ...prev, isOpen: false }))
        }
      },
    })
  }


  const loadHistory = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchValidationHistory({
        limit: 50,
        sourcePath: pairFilter.source.trim() || undefined,
        targetPath: pairFilter.target.trim() || undefined,
      })
      setItems(Array.isArray(data.items) ? data.items : [])
      setTotal(data.total ?? 0)
    } catch (e) {
      setItems([])
      setTotal(0)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [pairFilter.source, pairFilter.target])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  const mappingPairs = useMemo(() => {
    const seen = new Map()
    for (const row of items) {
      const key = `${row.source_path || row.source_filename}|${row.target_path || row.target_filename}`
      if (!seen.has(key)) seen.set(key, row)
    }
    return [...seen.values()]
  }, [items])

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
              <button
                type="button"
                className="btn btn-secondary"
                style={{ color: 'var(--danger)', borderColor: 'var(--danger-border)', background: 'var(--danger-muted)', height: 32, padding: '0 10px', fontSize: 12, fontWeight: 500 }}
                onClick={() => handleClearAll('mapping')}
              >
                Clear all mappings
              </button>
            ) : null}
          </div>
          {error ? <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p> : null}
          {loading ? <p style={{ color: 'var(--text-4)' }}>Loading…</p> : null}
          {!loading && !mappingPairs.length ? (
            <p style={{ color: 'var(--text-4)', marginBottom: 0 }}>No mapping history yet. Run a validation with persistence enabled.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {mappingPairs.map((row) => (
                <div
                  key={row.run_id}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter') { handleMappingClick(row) } }}
                  style={{
                    padding: 12,
                    cursor: loadingMappingId ? 'wait' : 'pointer',
                    borderRadius: 8,
                    border: '1px solid var(--border-1)',
                    opacity: loadingMappingId === row.run_id ? 0.7 : 1,
                    pointerEvents: loadingMappingId ? 'none' : 'auto',
                    transition: 'all 0.15s ease'
                  }}
                  onClick={() => handleMappingClick(row)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 13, color: 'var(--text-1)', fontWeight: 500 }}>
                      {basename(row.source_path || row.source_filename)} ↔ {basename(row.target_path || row.target_filename)}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      {loadingMappingId === row.run_id ? (
                        <span style={{ fontSize: 11, color: 'var(--text-3)' }}>Loading…</span>
                      ) : (
                        <StatusBadge isMatch={row.is_match} status={row.status} />
                      )}
                      <DeleteButton title="Delete mapping history" onClick={() => handleDeleteMapping(row)} />
                    </div>
                  </div>
                  <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--text-3)' }}>
                    {row.delimiter === 'fixed-width' || row.delimiter === 'fixed' ? (
                      <span style={{ color: 'var(--blue, #3b82f6)', fontWeight: 500 }}>Fixed-Width Date validation</span>
                    ) : (
                      <>
                        {row.mapping_count} mapping(s) · UID <code>{row.uid_column}</code>
                      </>
                    )}
                  </p>
                </div>
              ))}
            </div>

          )}
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
            {items.length ? (
              <button
                type="button"
                className="btn btn-secondary"
                style={{ color: 'var(--danger)', borderColor: 'var(--danger-border)', background: 'var(--danger-muted)', height: 32, padding: '0 10px', fontSize: 12, fontWeight: 500 }}
                onClick={() => handleClearAll('validation')}
              >
                Clear all history
              </button>
            ) : null}
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12, alignItems: 'flex-end' }}>
            <label style={{ fontSize: 12, color: 'var(--text-3)' }}>
              Source path
              <input
                type="text"
                value={pairFilter.source}
                onChange={(e) => setPairFilter((p) => ({ ...p, source: e.target.value }))}
                placeholder="/path/to/source.csv"
                style={{ display: 'block', marginTop: 4, minWidth: 220, padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border-1)' }}
              />
            </label>
            <label style={{ fontSize: 12, color: 'var(--text-3)' }}>
              Target path
              <input
                type="text"
                value={pairFilter.target}
                onChange={(e) => setPairFilter((p) => ({ ...p, target: e.target.value }))}
                placeholder="/path/to/target.csv"
                style={{ display: 'block', marginTop: 4, minWidth: 220, padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border-1)' }}
              />
            </label>
            <button type="button" className="btn btn-secondary" onClick={loadHistory} disabled={loading}>
              {loading ? 'Loading…' : 'Apply filter'}
            </button>
          </div>

          {error ? <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p> : null}

          {!loading && !items.length && !error ? (
            <p style={{ color: 'var(--text-4)', marginBottom: 0 }}>No validations recorded yet.</p>
          ) : null}

          {items.length ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--text-3)', borderBottom: '1px solid var(--border-1)' }}>
                    <th style={{ padding: '8px' }}>When</th>
                    <th style={{ padding: '8px' }}>Files</th>
                    <th style={{ padding: '8px' }}>Mappings</th>
                    <th style={{ padding: '8px' }}>Duration</th>
                    <th style={{ padding: '8px' }}>Result</th>
                    <th style={{ padding: '8px', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr
                      key={row.run_id}
                        role="button"
                        tabIndex={0}
                        onClick={() => handleOpenValidationReport(row)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            handleOpenValidationReport(row)
                          }
                        }}
                        style={{ borderTop: '1px solid var(--border-1)', cursor: openingRunId === row.run_id ? 'wait' : 'pointer' }}
                    >
                      <td style={{ padding: '8px', whiteSpace: 'nowrap' }}>
                        {row.completed_at ? new Date(row.completed_at).toLocaleString() : new Date(row.created_at).toLocaleString()}
                      </td>
                      <td style={{ padding: '8px' }}>
                        {basename(row.source_path || row.source_filename)}
                        <br />
                        <span style={{ color: 'var(--text-4)', fontSize: 11 }}>→ {basename(row.target_path || row.target_filename)}</span>
                        {(row.delimiter === 'fixed-width' || row.delimiter === 'fixed') && (
                          <span style={{ display: 'block', fontSize: 10, color: 'var(--blue, #3b82f6)', fontWeight: 600, marginTop: 2 }}>
                            Fixed-Width Format
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '8px' }}>
                        {row.delimiter === 'fixed-width' || row.delimiter === 'fixed' ? 'Date slice' : row.mapping_count}
                      </td>
                      <td style={{ padding: '8px' }}>{formatDuration(row.durations?.validation_seconds ?? row.durations?.total_seconds)}</td>
                      <td style={{ padding: '8px' }}><StatusBadge isMatch={row.is_match} status={row.status} /></td>
                      <td style={{ padding: '8px', textAlign: 'right' }}>
                        <DeleteButton title="Delete validation run" onClick={() => handleDeleteRun(row)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ margin: '8px 0 0', fontSize: 11, color: 'var(--text-4)' }}>{items.length} shown · {total} total</p>
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