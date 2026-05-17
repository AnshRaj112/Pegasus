const MOCK_COLUMNS = {
  source: ['id', 'customer_name', 'email', 'phone', 'address', 'city', 'country', 'zip_code', 'created_at', 'status'],
  target: ['record_id', 'full_name', 'email_address', 'contact_number', 'street', 'city', 'country', 'postal_code', 'signup_date', 'account_status'],
}

const ROW_COLORS = [
  '#f97316','#3b82f6','#22c55e','#a855f7','#ec4899',
  '#14b8a6','#eab308','#ef4444','#6366f1','#84cc16',
]

export default function Step3_Configure({ sourcePath, targetPath, mappings, onMappingChange, uidColumn, onUidColumnChange }) {
  const srcCols = MOCK_COLUMNS.source
  const tgtCols = MOCK_COLUMNS.target

  const activeMappings = mappings.length > 0 ? mappings : srcCols.map((col, i) => ({
    id: i, sourceCol: col, targetCol: tgtCols[i] ?? '', color: ROW_COLORS[i % ROW_COLORS.length],
  }))

  function handleTargetChange(id, val) {
    onMappingChange(activeMappings.map(m => m.id === id ? { ...m, targetCol: val } : m))
  }
  function addMapping() {
    const used = new Set(activeMappings.map(m => m.sourceCol))
    const next = srcCols.find(c => !used.has(c)) ?? ''
    onMappingChange([...activeMappings, {
      id: Date.now(), sourceCol: next, targetCol: '',
      color: ROW_COLORS[activeMappings.length % ROW_COLORS.length],
    }])
  }
  function removeMapping(id) {
    onMappingChange(activeMappings.filter(m => m.id !== id))
  }

  const mapped   = activeMappings.filter(m => m.targetCol).length
  const unmapped = activeMappings.length - mapped

  return (
    <div style={{ animation: 'fade-in 0.2s ease' }}>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
          Step 2 of 3
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 6 }}>
          Configure column mapping
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)' }}>
          Map each source column to its corresponding target column. Unmapped columns are skipped.
        </p>
      </div>

      {/* File summary row */}
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

      {/* UID column + stats */}
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
            {srcCols.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 14, fontSize: 12, color: 'var(--text-3)' }}>
          <span><strong style={{ color: 'var(--text-1)', fontWeight: 600 }}>{mapped}</strong> mapped</span>
          {unmapped > 0 && <span><strong style={{ color: 'var(--danger)', fontWeight: 600 }}>{unmapped}</strong> unmapped</span>}
          <span><strong style={{ color: 'var(--text-2)', fontWeight: 600 }}>{activeMappings.length}</strong> total</span>
        </div>
      </div>

      {/* Mapping table */}
      <div style={{ border: '1px solid var(--border-1)', borderRadius: 10, overflow: 'hidden' }}>
        {/* Table header */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 28px 1fr 28px',
          padding: '8px 14px',
          background: 'var(--surface-2)',
          borderBottom: '1px solid var(--border-1)',
          alignItems: 'center', gap: 8,
        }}>
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)' }}>Source</span>
          <div />
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)' }}>Target</span>
          <div />
        </div>

        {/* Rows */}
        <div>
          {activeMappings.map((m, idx) => (
            <div
              key={m.id}
              className="mapping-row"
              style={{
                display: 'grid', gridTemplateColumns: '1fr 28px 1fr 28px',
                padding: '6px 14px', gap: 8, alignItems: 'center',
                background: 'var(--surface-1)',
                borderBottom: idx < activeMappings.length - 1 ? '1px solid var(--border-1)' : 'none',
              }}
            >
              {/* Source */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: m.color, flexShrink: 0 }} />
                <select
                  value={m.sourceCol}
                  onChange={e => {
                    onMappingChange(activeMappings.map(x => x.id === m.id ? { ...x, sourceCol: e.target.value } : x))
                  }}
                  className="input input-mono"
                  style={{ height: 28, fontSize: 12, padding: '0 24px 0 8px',
                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12' fill='none'%3E%3Cpath d='M3 4.5l3 3 3-3' stroke='%2371717a' stroke-width='1.3' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
                    backgroundRepeat: 'no-repeat', backgroundPosition: 'right 6px center',
                  }}
                >
                  {srcCols.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              {/* Arrow */}
              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ color: 'var(--text-4)' }}>
                  <path d="M3 7h8M8 4.5L10.5 7 8 9.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>

              {/* Target */}
              <select
                value={m.targetCol}
                onChange={e => handleTargetChange(m.id, e.target.value)}
                className="input input-mono"
                style={{
                  height: 28, fontSize: 12, padding: '0 24px 0 8px',
                  borderColor: m.targetCol ? 'var(--border-2)' : 'var(--danger-border)',
                  color: m.targetCol ? 'var(--text-1)' : 'var(--danger)',
                  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12' fill='none'%3E%3Cpath d='M3 4.5l3 3 3-3' stroke='%2371717a' stroke-width='1.3' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
                  backgroundRepeat: 'no-repeat', backgroundPosition: 'right 6px center',
                }}
              >
                <option value="">— unmapped —</option>
                {tgtCols.map(c => <option key={c} value={c}>{c}</option>)}
              </select>

              {/* Remove */}
              <button
                type="button"
                onClick={() => removeMapping(m.id)}
                className="remove-btn"
                style={{
                  width: 24, height: 24, borderRadius: 5,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  color: 'var(--text-4)',
                  opacity: 0, transition: 'opacity 0.12s, color 0.12s',
                }}
                title="Remove"
                onMouseEnter={e => e.currentTarget.style.color = 'var(--danger)'}
                onMouseLeave={e => e.currentTarget.style.color = 'var(--text-4)'}
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
          ))}
        </div>

        {/* Add row */}
        <button
          type="button"
          onClick={addMapping}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 6,
            padding: '9px 14px', borderTop: '1px solid var(--border-1)',
            background: 'var(--surface-2)', border: 'none', borderTop: '1px solid var(--border-1)',
            color: 'var(--text-3)', fontSize: 12, fontWeight: 500,
            cursor: 'pointer', transition: 'all 0.12s', fontFamily: 'inherit',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-1)'; e.currentTarget.style.background = 'var(--surface-3)' }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)'; e.currentTarget.style.background = 'var(--surface-2)' }}
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <path d="M6.5 2v9M2 6.5h9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          Add mapping row
        </button>
      </div>

      {/* Hover helper for remove buttons */}
      <style>{`
        .mapping-row:hover .remove-btn { opacity: 1 !important; }
      `}</style>
    </div>
  )
}
