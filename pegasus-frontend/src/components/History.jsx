import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  basename,
  fetchValidationHistory,
  fetchValidationHistoryDetail,
  fetchValidationHistoryMismatches,
  formatDuration,
} from '../api/validationHistory'

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

export default function History() {
  const [topTab, setTopTab] = useState('validation')
  const [pairFilter, setPairFilter] = useState({ source: '', target: '' })
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedRunId, setSelectedRunId] = useState(null)

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
      {/* <Panel style={{ marginBottom: 12, padding: '12px 16px', fontSize: 12, color: 'var(--text-3)' }}>
        History is stored in PostgreSQL when <code style={{ fontSize: 11 }}>PEGASUS_ENABLE_VALIDATION_PERSISTENCE=true</code> and migrations are applied.
      </Panel> */}

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <TabButton active={topTab === 'mapping'} onClick={() => setTopTab('mapping')}>Mapping History</TabButton>
        <TabButton active={topTab === 'validation'} onClick={() => setTopTab('validation')}>Validation History</TabButton>
      </div>

      {topTab === 'mapping' ? (
        <Panel>
          <h4 style={{ margin: '0 0 8px', fontSize: 15, color: 'var(--text-1)' }}>Saved mappings by file pair</h4>
          <p style={{ marginTop: 0, fontSize: 13, color: 'var(--text-3)' }}>
            Latest validation run per source/target pair, including column mappings used.
          </p>
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
                  onKeyDown={(e) => { if (e.key === 'Enter') { setTopTab('validation'); setSelectedRunId(row.run_id) } }}
                  style={{ padding: 12, cursor: 'pointer', borderRadius: 8, border: '1px solid var(--border-1)' }}
                  onClick={() => { setTopTab('validation'); setSelectedRunId(row.run_id) }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 13, color: 'var(--text-1)' }}>
                      {basename(row.source_path || row.source_filename)} ↔ {basename(row.target_path || row.target_filename)}
                    </span>
                    <StatusBadge isMatch={row.is_match} status={row.status} />
                  </div>
                  <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--text-3)' }}>
                    {row.mapping_count} mapping(s) · UID <code>{row.uid_column}</code>
                  </p>
                </div>
              ))}
            </div>
          )}
        </Panel>
      ) : (
        <Panel>
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
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr
                      key={row.run_id}
                      onClick={() => setSelectedRunId(row.run_id)}
                      style={{ borderTop: '1px solid var(--border-1)', cursor: 'pointer' }}
                    >
                      <td style={{ padding: '8px', whiteSpace: 'nowrap' }}>
                        {row.completed_at ? new Date(row.completed_at).toLocaleString() : new Date(row.created_at).toLocaleString()}
                      </td>
                      <td style={{ padding: '8px' }}>
                        {basename(row.source_path || row.source_filename)}
                        <br />
                        <span style={{ color: 'var(--text-4)', fontSize: 11 }}>→ {basename(row.target_path || row.target_filename)}</span>
                      </td>
                      <td style={{ padding: '8px' }}>{row.mapping_count}</td>
                      <td style={{ padding: '8px' }}>{formatDuration(row.durations?.validation_seconds ?? row.durations?.total_seconds)}</td>
                      <td style={{ padding: '8px' }}><StatusBadge isMatch={row.is_match} status={row.status} /></td>
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
    </div>
  )
}
