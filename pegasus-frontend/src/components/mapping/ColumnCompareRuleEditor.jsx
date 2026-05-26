import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { clearCompareRule } from './columnMapping'

const COMPARE_MODES = [
  { value: 'auto', label: 'Default (auto)' },
  { value: 'custom', label: 'Custom expression' },
  { value: 'date', label: 'Date — calendar match' },
  { value: 'phone', label: 'Phone — digits only' },
  { value: 'digits', label: 'Digits only' },
  { value: 'text', label: 'Exact text' },
]

export default function ColumnCompareRuleEditor({
  row,
  rowId,
  onChange,
  onClose,
  anchorEl,
}) {
  const panelRef = useRef(null)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const [customExpressionDraft, setCustomExpressionDraft] = useState(row.customExpression || '')
  const [customExpressionSaved, setCustomExpressionSaved] = useState(false)

  useLayoutEffect(() => {
    if (!anchorEl) return
    const rect = anchorEl.getBoundingClientRect()
    const width = 300
    const panelHeight = 380
    const gap = 8
    const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))
    const spaceBelow = window.innerHeight - rect.bottom - gap
    const spaceAbove = rect.top - gap
    let top
    if (spaceBelow >= panelHeight || spaceBelow >= spaceAbove) {
      top = rect.bottom + gap
    } else {
      top = Math.max(12, rect.top - panelHeight - gap)
    }
    top = Math.min(top, window.innerHeight - panelHeight - 12)
    setPosition({ top: Math.max(12, top), left })
  }, [anchorEl])

  useEffect(() => {
    function handlePointerDown(event) {
      const target = event.target
      if (panelRef.current?.contains(target)) return
      if (target.closest?.(`[data-compare-rule-row="${rowId}"]`)) return
      onClose?.()
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') onClose?.()
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [rowId, onClose])

  useEffect(() => {
    setCustomExpressionDraft(row.customExpression || '')
    setCustomExpressionSaved(false)
  }, [row.customExpression, row.compareMode, rowId])

  function patch(fields) {
    onChange({ ...row, ...fields })
  }

  function handleSaveCustomExpression() {
    patch({ customExpression: customExpressionDraft.trim() })
    setCustomExpressionSaved(true)
  }

  const panel = (
    <div
      ref={panelRef}
      style={{
        position: 'fixed',
        top: position.top,
        left: position.left,
        zIndex: 2000,
        width: 300,
        maxHeight: 'min(70vh, 420px)',
        overflowY: 'auto',
        padding: '12px 14px',
        borderRadius: 10,
        background: 'var(--surface-1)',
        border: '1px solid var(--border-2)',
        boxShadow: '0 12px 40px rgba(0,0,0,0.18)',
        animation: 'fade-in 0.15s ease',
      }}
      role="dialog"
      aria-label={`Compare rules for ${row.sourceCol}`}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10, gap: 8 }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-1)' }}>Custom compare</div>
          <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 2 }}>
            {row.sourceCol} → {row.targetCol}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-4)', fontSize: 16, lineHeight: 1, padding: 0,
          }}
        >
          ×
        </button>
      </div>

      <p style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 10, lineHeight: 1.45 }}>
        Applies to this column pair only. Use the transform fields below to remove or add text on either side before validation.
      </p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ height: 26, fontSize: 11, padding: '0 8px' }}
          onClick={() => patch({ compareMode: 'phone', sourceStripPrefix: '+91', targetStripPrefix: '' })}
        >
          Phone (+91)
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ height: 26, fontSize: 11, padding: '0 8px' }}
          onClick={() => patch({ compareMode: 'date', sourceDateFormat: '%Y-%m-%d', targetDateFormat: '%d-%m-%Y' })}
        >
          Date formats
        </button>
      </div>

      <label style={{ display: 'block', marginBottom: 8 }}>
        <span style={{ display: 'block', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-4)', marginBottom: 4 }}>
          Compare mode
        </span>
        <select
          value={row.compareMode || 'auto'}
          onChange={e => patch({ compareMode: e.target.value })}
          className="input input-mono"
          style={{ width: '100%', height: 30, fontSize: 12 }}
        >
          {COMPARE_MODES.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </label>

      {row.compareMode === 'custom' && (
        <div style={{ marginBottom: 8 }}>
          <label style={{ display: 'block', marginBottom: 4 }}>
            <span style={{ display: 'block', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-4)', marginBottom: 4 }}>
              Custom expression
            </span>
            <input
              type="text"
              value={customExpressionDraft}
              onChange={e => {
                setCustomExpressionDraft(e.target.value)
                setCustomExpressionSaved(false)
              }}
              className="input input-mono"
              placeholder="Enter the expression"
              style={{ width: '100%', height: 30, fontSize: 12 }}
            />
          </label>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              {customExpressionSaved && (
                <span style={{ fontSize: 11, color: 'var(--success)', fontWeight: 600 }}>
                  Saved the expression.
                </span>
              )}
            </div>
            <button
              type="button"
              className="btn btn-primary"
              style={{ height: 28, padding: '0 10px', fontSize: 11, marginLeft: 'auto' }}
              onClick={handleSaveCustomExpression}
              disabled={!customExpressionDraft.trim()}
            >
              Save expression
            </button>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-4)', lineHeight: 1.45 }}>
            Use this field to describe the custom removal or addition you want to apply for this mapping.
          </div>
        </div>
      )}

      {row.compareMode === 'date' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 8 }}>
          <input
            type="text"
            placeholder="Source %d-%m-%Y"
            value={row.sourceDateFormat || ''}
            onChange={e => patch({ sourceDateFormat: e.target.value })}
            className="input input-mono"
            style={{ height: 28, fontSize: 11 }}
          />
          <input
            type="text"
            placeholder="Target %Y-%m-%d"
            value={row.targetDateFormat || ''}
            onChange={e => patch({ targetDateFormat: e.target.value })}
            className="input input-mono"
            style={{ height: 28, fontSize: 11 }}
          />
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
        <input
          type="text"
          placeholder="Remove from source (e.g. +91)"
          value={row.sourceStripPrefix || ''}
          onChange={e => patch({ sourceStripPrefix: e.target.value })}
          className="input input-mono"
          style={{ height: 28, fontSize: 11 }}
        />
        <input
          type="text"
          placeholder="Remove from target (optional)"
          value={row.targetStripPrefix || ''}
          onChange={e => patch({ targetStripPrefix: e.target.value })}
          className="input input-mono"
          style={{ height: 28, fontSize: 11 }}
        />
        {row.compareMode === 'auto' && (row.sourceStripPrefix || row.targetStripPrefix) && (
          <span style={{ fontSize: 10, color: 'var(--text-4)' }}>
            Tip: use Phone mode to compare digits only after stripping prefix.
          </span>
        )}
      </div>

      <details style={{ marginBottom: 8 }}>
        <summary style={{ fontSize: 11, color: 'var(--text-3)', cursor: 'pointer', userSelect: 'none' }}>
          Source transform
        </summary>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
          <input
            type="text"
            placeholder="Source regex pattern"
            value={row.sourceRegexPattern || ''}
            onChange={e => patch({ sourceRegexPattern: e.target.value })}
            className="input input-mono"
            style={{ height: 28, fontSize: 11 }}
          />
          <input
            type="text"
            placeholder="Source replacement"
            value={row.sourceRegexReplacement || ''}
            onChange={e => patch({ sourceRegexReplacement: e.target.value })}
            className="input input-mono"
            style={{ height: 28, fontSize: 11 }}
          />
          <div style={{ fontSize: 10, color: 'var(--text-4)', lineHeight: 1.45 }}>
            Example: pattern <span style={{ fontFamily: 'Geist Mono, monospace' }}>^</span> with replacement <span style={{ fontFamily: 'Geist Mono, monospace' }}>Mr. </span> adds text at the start. Pattern <span style={{ fontFamily: 'Geist Mono, monospace' }}>\s+</span> with replacement <span style={{ fontFamily: 'Geist Mono, monospace' }}>{' '}</span> normalizes whitespace.
          </div>
        </div>
      </details>

      <details style={{ marginBottom: 8 }}>
        <summary style={{ fontSize: 11, color: 'var(--text-3)', cursor: 'pointer', userSelect: 'none' }}>
          Target transform
        </summary>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
          <input
            type="text"
            placeholder="Target regex pattern"
            value={row.targetRegexPattern || ''}
            onChange={e => patch({ targetRegexPattern: e.target.value })}
            className="input input-mono"
            style={{ height: 28, fontSize: 11 }}
          />
          <input
            type="text"
            placeholder="Target replacement (use ^ or $ to add text)"
            value={row.targetRegexReplacement || ''}
            onChange={e => patch({ targetRegexReplacement: e.target.value })}
            className="input input-mono"
            style={{ height: 28, fontSize: 11 }}
          />
          <div style={{ fontSize: 10, color: 'var(--text-4)', lineHeight: 1.45 }}>
            Use this when the target needs cleanup or enrichment before comparison, such as removing separators or adding a fixed prefix.
          </div>
        </div>
      </details>

      <button
        type="button"
        className="btn btn-ghost"
        style={{ width: '100%', height: 30, fontSize: 11 }}
        onClick={() => {
          onChange(clearCompareRule(row))
          onClose?.()
        }}
      >
        Reset to default matching
      </button>
    </div>
  )

  return createPortal(panel, document.body)
}
