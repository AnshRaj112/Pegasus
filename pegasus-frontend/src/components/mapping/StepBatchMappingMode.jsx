const COPY = {
  csv: {
    stepLabel: 'Column mapping strategy',
    heading: pairCount => `How should columns be mapped across ${pairCount} file pairs?`,
    sub: 'Choose whether one shared mapping is enough, or each file needs its own configuration.',
    templateTitle: 'Same mapping for all files',
    templateDesc:
      'Define column mapping once using the first file pair, then apply it to every pair. You only map files where columns do not match the template.',
    manualTitle: 'Map each file manually',
    manualDesc: 'Walk through every file pair one by one and configure column mapping separately.',
  },
  'fixed-width': {
    stepLabel: 'Layout strategy',
    heading: pairCount => `How should fixed-width fields be configured across ${pairCount} file pairs?`,
    sub: 'Use one shared field layout (join column, date handling, compared fields) or configure each pair separately.',
    templateTitle: 'Same layout for all files',
    templateDesc:
      'Configure fields on the first pair, then apply join column and field selection to every pair. Slice positions are re-detected per file; only pairs that do not match need manual setup.',
    manualTitle: 'Configure each file manually',
    manualDesc: 'Walk through every file pair and set join column, date formats, and fields separately.',
  },
  json: {
    stepLabel: 'Batch review strategy',
    heading: pairCount => `How should ${pairCount} JSON file pairs be processed?`,
    sub: 'JSON uses semantic comparison with no column mapping. Choose whether to confirm all pairs at once or step through each pair.',
    templateTitle: 'Apply to all files at once',
    templateDesc:
      'Skip per-file setup and go straight to review — all pairs use the same JSON comparison settings.',
    manualTitle: 'Review each pair manually',
    manualDesc: 'Step through every file pair to confirm source and target paths before running validation.',
  },
}

const MODES = ['template', 'manual']

export default function StepBatchMappingMode({ pairCount, fileFormat = 'csv', onSelect, onBack }) {
  const copy = COPY[fileFormat] || COPY.csv
  return (
    <div style={{ animation: 'fade-in 0.2s ease' }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
          {copy.stepLabel}
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', marginBottom: 6 }}>
          {copy.heading(pairCount)}
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.5, margin: 0 }}>
          {copy.sub}
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
        {MODES.map(modeId => (
          <button
            key={modeId}
            type="button"
            onClick={() => onSelect(modeId)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-start',
              gap: 8,
              padding: 16,
              borderRadius: 10,
              border: '1px solid var(--border-1)',
              background: 'var(--surface-1)',
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>
              {modeId === 'template' ? copy.templateTitle : copy.manualTitle}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.45 }}>
              {modeId === 'template' ? copy.templateDesc : copy.manualDesc}
            </div>
          </button>
        ))}
      </div>

      <div style={{ marginTop: 20 }}>
        <button type="button" onClick={onBack} className="btn btn-ghost">Back to file pairing</button>
      </div>
    </div>
  )
}
