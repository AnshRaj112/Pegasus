import { useMemo, useState } from 'react'

function newUnitId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `unit-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export default function StepFilePairing({
  pairs,
  unmatchedSources,
  unmatchedTargets,
  onChange,
  onBack,
  onContinue,
}) {
  const [draft, setDraft] = useState(() => ({
    pairs: pairs.map(p => ({ ...p })),
    unmatchedSources: [...unmatchedSources],
    unmatchedTargets: [...unmatchedTargets],
  }))

  const allPaired = draft.pairs.length > 0
    && draft.unmatchedSources.length === 0
    && draft.unmatchedTargets.length === 0

  const sourceOptions = useMemo(
    () => draft.unmatchedSources.map(p => ({ path: p, name: p.split('/').pop() || p })),
    [draft.unmatchedSources],
  )
  const targetOptions = useMemo(
    () => draft.unmatchedTargets.map(p => ({ path: p, name: p.split('/').pop() || p })),
    [draft.unmatchedTargets],
  )

  function commit(next) {
    setDraft(next)
    onChange?.(next)
  }

  function removePair(unitId) {
    const pair = draft.pairs.find(p => p.unit_id === unitId)
    if (!pair) return
    commit({
      pairs: draft.pairs.filter(p => p.unit_id !== unitId),
      unmatchedSources: [...draft.unmatchedSources, pair.source_path],
      unmatchedTargets: [...draft.unmatchedTargets, pair.target_path],
    })
  }

  function addManualPair(sourcePath, targetPath) {
    if (!sourcePath || !targetPath) return
    commit({
      pairs: [
        ...draft.pairs,
        {
          unit_id: newUnitId(),
          source_path: sourcePath,
          target_path: targetPath,
          source_name: sourcePath.split('/').pop() || sourcePath,
          target_name: targetPath.split('/').pop() || targetPath,
          auto_matched: false,
        },
      ],
      unmatchedSources: draft.unmatchedSources.filter(p => p !== sourcePath),
      unmatchedTargets: draft.unmatchedTargets.filter(p => p !== targetPath),
    })
  }

  const [manualSource, setManualSource] = useState('')
  const [manualTarget, setManualTarget] = useState('')

  return (
    <div style={{ animation: 'fade-in 0.2s ease', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
          Step 2 — File pairing
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', marginBottom: 4 }}>Confirm file pairs</h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)' }}>
          Files were auto-matched by filename. Adjust pairs below or manually match unmatched files.
        </p>
      </div>

      <div style={{ border: '1px solid var(--border-1)', borderRadius: 10, overflow: 'hidden' }}>
        <div style={{ padding: '10px 14px', background: 'var(--surface-2)', borderBottom: '1px solid var(--border-1)', fontSize: 12, fontWeight: 600, color: 'var(--text-2)' }}>
          Paired files ({draft.pairs.length})
        </div>
        {draft.pairs.length === 0 ? (
          <div style={{ padding: 20, fontSize: 13, color: 'var(--text-4)' }}>No pairs yet. Match files manually below.</div>
        ) : (
          draft.pairs.map(pair => (
            <div
              key={pair.unit_id}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr auto 1fr auto',
                gap: 10,
                alignItems: 'center',
                padding: '10px 14px',
                borderBottom: '1px solid var(--border-1)',
                fontSize: 12,
              }}
            >
              <code style={{ fontFamily: 'Geist Mono, monospace', color: 'var(--text-2)', wordBreak: 'break-all' }}>{pair.source_name}</code>
              <span style={{ color: 'var(--text-4)' }}>→</span>
              <code style={{ fontFamily: 'Geist Mono, monospace', color: 'var(--text-2)', wordBreak: 'break-all' }}>{pair.target_name}</code>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                {pair.auto_matched ? (
                  <span style={{ fontSize: 10, color: 'var(--success)', fontWeight: 600 }}>auto</span>
                ) : (
                  <span style={{ fontSize: 10, color: 'var(--text-4)' }}>manual</span>
                )}
                <button type="button" className="btn btn-ghost" style={{ height: 26, padding: '0 8px', fontSize: 11 }} onClick={() => removePair(pair.unit_id)}>
                  Unpair
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {(sourceOptions.length > 0 || targetOptions.length > 0) && (
        <div style={{ padding: 16, borderRadius: 10, border: '1px solid var(--border-1)', background: 'var(--surface-2)' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', marginBottom: 10 }}>Manual match</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 10, alignItems: 'end' }}>
            <label>
              <span style={{ display: 'block', fontSize: 11, color: 'var(--text-4)', marginBottom: 4 }}>Unmatched source</span>
              <select className="input" value={manualSource} onChange={e => setManualSource(e.target.value)} style={{ width: '100%', height: 34 }}>
                <option value="">Select…</option>
                {sourceOptions.map(o => (
                  <option key={o.path} value={o.path}>{o.name}</option>
                ))}
              </select>
            </label>
            <label>
              <span style={{ display: 'block', fontSize: 11, color: 'var(--text-4)', marginBottom: 4 }}>Unmatched target</span>
              <select className="input" value={manualTarget} onChange={e => setManualTarget(e.target.value)} style={{ width: '100%', height: 34 }}>
                <option value="">Select…</option>
                {targetOptions.map(o => (
                  <option key={o.path} value={o.path}>{o.name}</option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!manualSource || !manualTarget}
              onClick={() => {
                addManualPair(manualSource, manualTarget)
                setManualSource('')
                setManualTarget('')
              }}
            >
              Pair
            </button>
          </div>
          {!allPaired && (
            <p style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 10, marginBottom: 0 }}>
              Unmatched: {draft.unmatchedSources.length} source, {draft.unmatchedTargets.length} target
              {draft.pairs.length > 0 ? ' — you can continue with current pairs only.' : ''}
            </p>
          )}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <button type="button" onClick={onBack} className="btn btn-ghost">Back</button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={draft.pairs.length === 0}
          onClick={() => onContinue(draft.pairs)}
        >
          Continue to column mapping
        </button>
      </div>
    </div>
  )
}
