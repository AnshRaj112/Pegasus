const MODES = [
  {
    id: 'template',
    title: 'Same mapping for all files',
    description:
      'Define column mapping once using the first file pair, then apply it to every pair. You only map files where columns do not match the template.',
  },
  {
    id: 'manual',
    title: 'Map each file manually',
    description:
      'Walk through every file pair one by one and configure column mapping separately.',
  },
]

export default function StepBatchMappingMode({ pairCount, onSelect, onBack }) {
  return (
    <div style={{ animation: 'fade-in 0.2s ease' }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
          Column mapping strategy
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', marginBottom: 6 }}>
          How should columns be mapped across {pairCount} file pairs?
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.5, margin: 0 }}>
          Choose whether one shared mapping is enough, or each file needs its own configuration.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
        {MODES.map(mode => (
          <button
            key={mode.id}
            type="button"
            onClick={() => onSelect(mode.id)}
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
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>{mode.title}</div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.45 }}>{mode.description}</div>
          </button>
        ))}
      </div>

      <div style={{ marginTop: 20 }}>
        <button type="button" onClick={onBack} className="btn btn-ghost">Back to file pairing</button>
      </div>
    </div>
  )
}
