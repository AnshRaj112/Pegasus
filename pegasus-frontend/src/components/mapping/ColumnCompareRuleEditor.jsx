import { useEffect, useRef } from 'react'
import { clearCompareRule } from './columnMapping'

const COMPARE_MODES = [
  { value: 'auto', label: 'Default (auto)' },
  { value: 'date', label: 'Date — calendar match' },
  { value: 'phone', label: 'Phone — digits only' },
  { value: 'digits', label: 'Digits only' },
  { value: 'text', label: 'Exact text' },
]

export default function ColumnCompareRuleEditor({
  row,
  onChange,
  onClose,
  anchorRef,
}) {
  const panelRef = useRef(null)

  useEffect(() => {
    function handlePointerDown(event) {
      const target = event.target
      if (panelRef.current?.contains(target)) return
      if (anchorRef?.current?.contains(target)) return
      onClose?.()
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [anchorRef, onClose])

  function patch(fields) {
    onChange({ ...row, ...fields })
  }

  return (
    <div
      ref={panelRef}
      style={{
        position: 'absolute',
        top: '100%',
        right: 0,
        marginTop: 6,
        zIndex: 20,
        width: 300,
        padding: '12px 14px',
        borderRadius: 10,
        background: 'var(--surface-1)',
        border: '1px solid var(--border-2)',
        boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
        animation: 'fade-in 0.15s ease',
      }}
      role="dialog"
      aria-label={`Compare rules for ${row.sourceCol}`}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10, gap: 8 }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-1)' }}>
            Custom compare
          </div>
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
        Other columns use default matching. Only this field uses the rules below.
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
          placeholder="Remove from source before compare (e.g. +91)"
          value={row.sourceStripPrefix || ''}
          onChange={e => patch({ sourceStripPrefix: e.target.value })}
          className="input input-mono"
          style={{ height: 28, fontSize: 11 }}
        />
        <input
          type="text"
          placeholder="Remove from target before compare (optional)"
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
          Advanced regex
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
}
