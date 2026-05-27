/**
 * Side-by-side sample values for UID and mapped source/target columns before validation.
 */

function PreviewBlock({ subtitle, sourceCol, targetCol, sourceSamples, targetSamples, displayRows, accent }) {
  const srcVals = sourceSamples[sourceCol] || []
  const tgtVals = targetSamples[targetCol] || []
  return (
    <div style={{ borderTop: '1px solid var(--border-1)', paddingTop: 12 }}>
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-1)', fontFamily: 'Geist Mono, monospace' }}>
          {sourceCol}
          {targetCol !== sourceCol && (
            <>
              <span style={{ color: 'var(--text-4)', fontWeight: 400, margin: '0 6px' }}>→</span>
              {targetCol}
            </>
          )}
        </div>
        {subtitle && (
          <div style={{ fontSize: 11, color: accent ? 'var(--accent)' : 'var(--text-4)', marginTop: 2 }}>
            {subtitle}
          </div>
        )}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {[{ label: 'Source', values: srcVals }, { label: 'Target', values: tgtVals }].map(({ label, values }) => (
          <div key={label}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 4 }}>
              {label}
            </div>
            <div style={{
              borderRadius: 8,
              border: `1px solid ${accent ? 'var(--accent-border)' : 'var(--border-1)'}`,
              background: 'var(--surface-1)',
              overflow: 'hidden',
            }}>
              {Array.from({ length: displayRows }, (_, i) => (
                <div
                  key={i}
                  style={{
                    padding: '5px 8px',
                    fontSize: 11,
                    fontFamily: 'Geist Mono, monospace',
                    color: values[i] != null && values[i] !== '' ? 'var(--text-2)' : 'var(--text-4)',
                    borderBottom: i < displayRows - 1 ? '1px solid var(--border-1)' : 'none',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={values[i] ?? ''}
                >
                  {values[i] != null && values[i] !== '' ? values[i] : '—'}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function MappingColumnPreview({
  uidColumn = '',
  hasHeader = true,
  mappings = [],
  sourceSamples = {},
  targetSamples = {},
  sampleRowCount = 6,
}) {
  const mapped = mappings.filter(m => m.targetCol && m.sourceCol)
  const uid = String(uidColumn || '').trim()
  const showUid = Boolean(uid)
  if (!showUid && mapped.length === 0) return null

  const sampleLengths = [
    ...(showUid ? [
      (sourceSamples[uid] || []).length,
      (targetSamples[uid] || []).length,
    ] : []),
    ...mapped.flatMap(m => [
      (sourceSamples[m.sourceCol] || []).length,
      (targetSamples[m.targetCol] || []).length,
    ]),
  ]
  const rowCount = sampleLengths.length > 0 ? Math.max(sampleRowCount, ...sampleLengths) : sampleRowCount
  const displayRows = Math.min(rowCount, sampleRowCount)

  return (
    <div style={{
      marginBottom: 16,
      padding: '12px 14px',
      borderRadius: 10,
      background: 'var(--surface-2)',
      border: '1px solid var(--border-1)',
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 8 }}>
        Column preview (first {displayRows} rows)
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 0, marginBottom: 12 }}>
        {hasHeader
          ? 'Confirm the join key and each mapping. Rows are matched by the selected UID column; columns are paired by name where mapped.'
          : 'Confirm the join key and each mapping. Files have no header row (positional column names); rows are matched by UID, not line number.'}
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {showUid && (
          <PreviewBlock
            subtitle={hasHeader
              ? 'UID / join key — match rows by this column name'
              : 'UID / join key — match rows by this field (positional column)'}
            sourceCol={uid}
            targetCol={uid}
            sourceSamples={sourceSamples}
            targetSamples={targetSamples}
            displayRows={displayRows}
            accent
          />
        )}
        {mapped.map(m => (
          <PreviewBlock
            key={m.id}
            sourceCol={m.sourceCol}
            targetCol={m.targetCol}
            sourceSamples={sourceSamples}
            targetSamples={targetSamples}
            displayRows={displayRows}
          />
        ))}
      </div>
    </div>
  )
}
