import { useState } from 'react'
import ColumnCompareRuleEditor from './ColumnCompareRuleEditor'
import CompareRuleIconButton from './CompareRuleIconButton'
import { mappingHasCustomRule } from './columnMapping'

const MAPPING_GRID = 'minmax(0, 1fr) 28px minmax(0, 1fr) 32px'

export default function Step3_Configure({
  sourcePath,
  targetPath,
  sourceColumns = [],
  targetColumns = [],
  compareColumns = [],
  previewLoading = false,
  previewError = '',
  unmatchedSourceColumns = [],
  unmatchedTargetColumns = [],
  mappings = [],
  onMappingChange,
  uidColumn,
  onUidColumnChange,
  validateHeaderFormats = false,
  onValidateHeaderFormatsChange,
  validateFooters = false,
  onValidateFootersChange,
  footerTrailingRows = 1,
  onFooterTrailingRowsChange,
  formatCheckBySource = new Map(),
  analyzeLoading = false,
  analyzeError = '',
  footerValidation = null,
}) {
  const activeMappings = mappings
  const mapped = activeMappings.filter(m => m.targetCol || (Array.isArray(m.targetCols) && m.targetCols.length > 0)).length
  const unmapped = Math.max(compareColumns.length - mapped, 0)
  const usedTargets = new Set(
    activeMappings.flatMap(m => [
      ...(m.targetCol ? [m.targetCol] : []),
      ...(Array.isArray(m.targetCols) ? m.targetCols : []),
    ]),
  )
  const uidRow = uidColumn ? { id: '__uid__', sourceCol: uidColumn, targetCol: uidColumn, targetCols: [uidColumn] } : null
  const [pendingAdditionalTargets, setPendingAdditionalTargets] = useState({})

  function handleTargetChange(id, val) {
    onMappingChange(activeMappings.map(m => {
      if (m.id !== id) return m
      const nextTarget = String(val || '').trim()
      const currentTargets = Array.isArray(m.targetCols) ? m.targetCols.filter(Boolean) : []
      const nextTargets = nextTarget
        ? [nextTarget, ...currentTargets.filter(col => col !== nextTarget)]
        : []
      return { ...m, targetCol: nextTarget, targetCols: nextTargets }
    }))
  }

  function handleAdditionalTargetChange(id, val) {
    const nextTarget = String(val || '').trim()
    if (!nextTarget) return
    onMappingChange(activeMappings.map(m => {
      if (m.id !== id) return m
      const currentTargets = Array.isArray(m.targetCols) ? m.targetCols.filter(Boolean) : []
      if (currentTargets.includes(nextTarget)) return m
      const primary = m.targetCol || currentTargets[0] || nextTarget
      const nextTargets = [primary, ...currentTargets.filter(col => col !== primary && col !== nextTarget), nextTarget]
      return { ...m, targetCol: primary, targetCols: nextTargets }
    }))
    setPendingAdditionalTargets(prev => ({ ...prev, [id]: '' }))
  }

  function handleTargetRemoval(id, targetToRemove) {
    onMappingChange(activeMappings.map(m => {
      if (m.id !== id) return m
      const currentTargets = Array.isArray(m.targetCols) ? m.targetCols.filter(Boolean) : []
      const nextTargets = currentTargets.filter(col => col !== targetToRemove)
      if (nextTargets.length === 0) {
        return { ...m, targetCol: '', targetCols: [] }
      }
      const nextPrimary = m.targetCol === targetToRemove ? nextTargets[0] : m.targetCol
      return {
        ...m,
        targetCol: nextPrimary,
        targetCols: nextPrimary
          ? [nextPrimary, ...nextTargets.filter(col => col !== nextPrimary)]
          : nextTargets,
      }
    }))
  }

  const [openRule, setOpenRule] = useState(null)
  const openRuleRow = openRule ? activeMappings.find(m => m.id === openRule.rowId) : null

  function toggleRuleEditor(row, anchorEl) {
    if (openRule?.rowId === row.id) {
      setOpenRule(null)
      return
    }
    setOpenRule({ rowId: row.id, anchorEl })
  }

  return (
    <div style={{ animation: 'fade-in 0.2s ease' }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
          Step 2 of 3
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 6 }}>
          Configure column mapping
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)', maxWidth: 760 }}>
          Map columns as usual. Use the rule icon beside source or target when that field needs custom matching
          (e.g. strip <code style={{ fontFamily: 'monospace' }}>+91</code> on source phone numbers).
        </p>
        <p style={{ fontSize: 12, color: 'var(--text-4)', maxWidth: 820, marginTop: 8 }}>
          A source column can keep extra target columns in the UI for grouped fields like first name + last name. The primary target still drives the current validation payload.
        </p>
      </div>

      {previewLoading && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
          padding: '11px 14px', borderRadius: 10,
          background: 'var(--accent-muted)', border: '1px solid var(--accent-border)',
          color: 'var(--accent)', fontSize: 13,
        }}>
          <span style={{
            width: 14, height: 14, borderRadius: '50%',
            border: '2px solid var(--accent-border)', borderTopColor: 'var(--accent)',
            animation: 'spin 0.7s linear infinite', display: 'inline-block', flexShrink: 0,
          }} />
          Reading source and target headers...
        </div>
      )}

      {previewError && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', borderRadius: 10,
          background: 'var(--danger-muted)', border: '1px solid var(--danger-border)',
          color: 'var(--danger)', fontSize: 12,
        }}>
          {previewError}
        </div>
      )}

      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16,
        padding: '12px 14px', borderRadius: 10,
        background: 'var(--surface-2)', border: '1px solid var(--border-1)',
      }}>
        {[{ label: 'Source', path: sourcePath }, { label: 'Target', path: targetPath }].map(({ label, path }) => (
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

      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12,
        padding: '10px 14px', borderRadius: 10,
        background: 'var(--surface-1)', border: '1px solid var(--border-1)',
        flexWrap: 'wrap',
      }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, flex: '0 0 auto' }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', letterSpacing: '-0.01em' }}>
            Join key (UID)
          </span>
          <select
            id="uid-col-select"
            value={uidColumn}
            onChange={e => onUidColumnChange(e.target.value)}
            className="input input-mono"
            style={{ width: 'auto', height: 30, fontSize: 12, padding: '0 28px 0 10px',
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12' fill='none'%3E%3Cpath d='M3 4.5l3 3 3-3' stroke='%2371717a' stroke-width='1.3' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
              backgroundRepeat: 'no-repeat', backgroundPosition: 'right 8px center',
            }}
          >
            <option value="">— select —</option>
            {sourceColumns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 14, fontSize: 12, color: 'var(--text-3)' }}>
          <span><strong style={{ color: 'var(--text-1)', fontWeight: 600 }}>{mapped}</strong> mapped</span>
          {unmapped > 0 && <span><strong style={{ color: 'var(--danger)', fontWeight: 600 }}>{unmapped}</strong> unmapped</span>}
          {unmatchedTargetColumns.length > 0 && <span><strong style={{ color: 'var(--text-2)', fontWeight: 600 }}>{unmatchedTargetColumns.length}</strong> target-only</span>}
          <span><strong style={{ color: 'var(--text-2)', fontWeight: 600 }}>{activeMappings.length}</strong> total</span>
        </div>
      </div>

      <div style={{
        marginBottom: 12, padding: '12px 14px', borderRadius: 10,
        background: 'var(--surface-2)', border: '1px solid var(--border-1)',
      }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 10 }}>
          Optional checks
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={validateHeaderFormats}
              onChange={e => onValidateHeaderFormatsChange?.(e.target.checked)}
              style={{ marginTop: 2 }}
            />
            <span>
              <strong style={{ color: 'var(--text-1)' }}>Validate column formats</strong>
              <span style={{ display: 'block', fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>
                Sample mapped columns and warn when source/target formats differ (dates, email, numbers, etc.).
              </span>
            </span>
          </label>
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, fontSize: 13, color: 'var(--text-2)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={validateFooters}
              onChange={e => onValidateFootersChange?.(e.target.checked)}
              style={{ marginTop: 2 }}
            />
            <span>
              <strong style={{ color: 'var(--text-1)' }}>Validate file footers</strong>
              <span style={{ display: 'block', fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>
                Compare trailing rows between source and target.
              </span>
            </span>
          </label>
          {validateFooters && (
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 26, fontSize: 12, color: 'var(--text-3)' }}>
              Trailing rows
              <input
                type="number"
                min={1}
                max={10}
                value={footerTrailingRows}
                onChange={e => onFooterTrailingRowsChange?.(Number(e.target.value) || 1)}
                className="input input-mono"
                style={{ width: 56, height: 28, fontSize: 12 }}
              />
            </label>
          )}
        </div>
        {analyzeLoading && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--accent)' }}>Running format/footer checks…</div>
        )}
        {analyzeError && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--danger)' }}>{analyzeError}</div>
        )}
        {validateFooters && footerValidation && !analyzeLoading && (
          <div style={{
            marginTop: 10, fontSize: 12,
            color: footerValidation.match ? 'var(--success)' : 'var(--danger)',
          }}>
            {footerValidation.match
              ? 'Footer rows match between source and target.'
              : (footerValidation.message || 'Footer rows do not match.')}
          </div>
        )}
      </div>

      {(unmatchedSourceColumns.length > 0 || unmatchedTargetColumns.length > 0) && (
        <div style={{
          display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12,
          padding: '10px 14px', borderRadius: 10,
          background: 'var(--surface-2)', border: '1px solid var(--border-1)',
          fontSize: 12, color: 'var(--text-3)',
        }}>
          {unmatchedSourceColumns.length > 0 && <span>{unmatchedSourceColumns.length} source column(s) still need a target mapping.</span>}
          {unmatchedTargetColumns.length > 0 && <span>{unmatchedTargetColumns.length} target column(s) are not matched yet.</span>}
        </div>
      )}

      <div style={{ border: '1px solid var(--border-1)', borderRadius: 10, overflow: 'visible' }}>
        <div style={{
          display: 'grid', gridTemplateColumns: MAPPING_GRID,
          padding: '8px 14px',
          background: 'var(--surface-2)',
          borderBottom: '1px solid var(--border-1)',
          borderRadius: '9px 9px 0 0',
          alignItems: 'center', gap: 8,
        }}>
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)' }}>Source</span>
          <div />
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)' }}>Target</span>
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', textAlign: 'center' }}>Status</span>
        </div>

        <div>
          {uidRow && (
            <div
              className="mapping-row"
              style={{
                display: 'grid', gridTemplateColumns: MAPPING_GRID,
                padding: '8px 14px', gap: 8, alignItems: 'center',
                background: 'var(--surface-2)',
                borderBottom: activeMappings.length > 0 ? '1px solid var(--border-1)' : 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--text-4)', flexShrink: 0 }} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={uidRow.sourceCol}>
                    {uidRow.sourceCol}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-4)' }}>UID / join key</div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ color: 'var(--text-4)' }}>
                  <path d="M3 7h8M8 4.5L10.5 7 8 9.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>

              <div style={{ minWidth: 0 }}>
                <div style={{
                  height: 28, padding: '0 8px', borderRadius: 8,
                  display: 'flex', alignItems: 'center',
                  background: 'var(--surface-1)', border: '1px solid var(--border-1)',
                  color: 'var(--text-2)', fontSize: 12, fontFamily: 'Geist Mono, monospace',
                }}>
                  {uidRow.targetCol}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-4)' }}>UID</span>
              </div>
            </div>
          )}
          {activeMappings.length > 0 ? activeMappings.map((m, idx) => {
            const currentTargets = Array.isArray(m.targetCols) && m.targetCols.length > 0
              ? m.targetCols
              : (m.targetCol ? [m.targetCol] : [])
            const additionalTargets = currentTargets.filter(col => col !== m.targetCol)
            const isMapped = currentTargets.length > 0
            const formatCheck = validateHeaderFormats && isMapped ? formatCheckBySource.get(m.sourceCol) : null
            const formatWarn = formatCheck && formatCheck.compatible === false
            const hasCustomRule = mappingHasCustomRule(m)
            const ruleOpen = openRule?.rowId === m.id
            const availableAdditionalTargets = targetColumns.filter(col => !currentTargets.includes(col) && !(usedTargets.has(col) && col !== m.targetCol))
            return (
              <div
                key={m.id}
                className="mapping-row"
                style={{
                  display: 'grid', gridTemplateColumns: MAPPING_GRID,
                  padding: '8px 14px', gap: 8, alignItems: 'center',
                  background: 'var(--surface-1)',
                  borderBottom: idx < activeMappings.length - 1 ? '1px solid var(--border-1)' : 'none',
                  borderRadius: idx === activeMappings.length - 1 ? '0 0 9px 9px' : undefined,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0 }} />
                  <div
                    style={{
                      flex: 1, minWidth: 0, fontSize: 12, fontWeight: 600, color: 'var(--text-1)',
                      fontFamily: 'Geist Mono, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}
                    title={m.sourceCol}
                  >
                    {m.sourceCol}
                  </div>
                  {isMapped && (
                    <span data-compare-rule-row={m.id}>
                      <CompareRuleIconButton
                        active={ruleOpen}
                        configured={hasCustomRule}
                        label={`Source rules for ${m.sourceCol}`}
                        onClick={e => toggleRuleEditor(m, e.currentTarget)}
                      />
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ color: 'var(--text-4)' }}>
                    <path d="M3 7h8M8 4.5L10.5 7 8 9.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>

                <div style={{ minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                    <select
                      value={m.targetCol}
                      onChange={e => handleTargetChange(m.id, e.target.value)}
                      disabled={previewLoading || targetColumns.length === 0}
                      className="input input-mono"
                      style={{
                        flex: 1, minWidth: 0, height: 28, fontSize: 12, padding: '0 24px 0 8px',
                        borderColor: isMapped ? 'var(--border-2)' : 'var(--danger-border)',
                        color: isMapped ? 'var(--text-1)' : 'var(--danger)',
                        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12' fill='none'%3E%3Cpath d='M3 4.5l3 3 3-3' stroke='%2371717a' stroke-width='1.3' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
                        backgroundRepeat: 'no-repeat', backgroundPosition: 'right 6px center',
                        backgroundColor: isMapped ? 'var(--surface-1)' : 'rgba(239, 68, 68, 0.06)',
                      }}
                    >
                      <option value="">— not mapped —</option>
                      {targetColumns.map(c => (
                        <option key={c} value={c} disabled={usedTargets.has(c) && c !== m.targetCol}>
                          {c}
                        </option>
                      ))}
                    </select>
                    {isMapped && (
                      <span data-compare-rule-row={m.id}>
                        <CompareRuleIconButton
                          active={ruleOpen}
                          configured={hasCustomRule}
                          label={`Target rules for ${m.targetCol}`}
                          onClick={e => toggleRuleEditor(m, e.currentTarget)}
                        />
                      </span>
                    )}
                  </div>
                  {isMapped && (
                    <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                      <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-4)' }}>
                        Additional targets
                      </span>
                      {additionalTargets.length > 0 ? additionalTargets.map(col => (
                        <span
                          key={`${m.id}-${col}`}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: 6,
                            padding: '3px 8px', borderRadius: 999,
                            background: 'var(--surface-2)', border: '1px solid var(--border-1)',
                            fontSize: 11, color: 'var(--text-2)', fontFamily: 'Geist Mono, monospace',
                          }}
                        >
                          {col}
                          <button
                            type="button"
                            onClick={() => handleTargetRemoval(m.id, col)}
                            style={{
                              border: 'none', background: 'transparent', cursor: 'pointer',
                              color: 'var(--text-4)', padding: 0, fontSize: 12, lineHeight: 1,
                            }}
                            aria-label={`Remove ${col} from ${m.sourceCol}`}
                          >
                            ×
                          </button>
                        </span>
                      )) : (
                        <span style={{ fontSize: 11, color: 'var(--text-4)' }}>None yet</span>
                      )}
                      {availableAdditionalTargets.length > 0 && (
                        <select
                          value={pendingAdditionalTargets[m.id] || ''}
                          onChange={e => handleAdditionalTargetChange(m.id, e.target.value)}
                          className="input input-mono"
                          style={{ height: 28, fontSize: 11, width: 'auto', minWidth: 180, paddingRight: 28 }}
                        >
                          <option value="">Add another target…</option>
                          {availableAdditionalTargets.map(c => (
                            <option key={c} value={c}>{c}</option>
                          ))}
                        </select>
                      )}
                    </div>
                  )}
                  {!isMapped && (
                    <div style={{ marginTop: 4, fontSize: 11, color: 'var(--danger)' }}>
                      Pick a target column to compare.
                    </div>
                  )}
                  {formatWarn && (
                    <div style={{ marginTop: 4, fontSize: 11, color: 'var(--danger)' }}>
                      Format: {formatCheck.source_format} → {formatCheck.target_format}. {formatCheck.message}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <span
                    style={{
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      width: 24, height: 24, borderRadius: 6, fontSize: 10, fontWeight: 700,
                      color: formatWarn ? 'var(--danger)' : isMapped ? 'var(--success)' : 'var(--danger)',
                      background: formatWarn ? 'var(--danger-muted)' : isMapped ? 'var(--success-muted)' : 'var(--danger-muted)',
                    }}
                    title={formatWarn ? formatCheck?.message : isMapped ? 'Mapped' : 'Unmapped'}
                  >
                    {formatWarn ? '!' : isMapped ? 'OK' : '!'}
                  </span>
                </div>

              </div>
            )
          }) : (
            <div style={{ padding: '18px 14px', color: 'var(--text-4)', fontSize: 12 }}>
              No source columns found yet. Finish loading the header preview to begin mapping.
            </div>
          )}
        </div>

        {openRuleRow && openRule?.anchorEl && (
          <ColumnCompareRuleEditor
            row={openRuleRow}
            rowId={openRuleRow.id}
            anchorEl={openRule.anchorEl}
            onChange={updated => onMappingChange(activeMappings.map(row => (row.id === openRuleRow.id ? updated : row)))}
            onClose={() => setOpenRule(null)}
          />
        )}
      </div>
    </div>
  )
}
