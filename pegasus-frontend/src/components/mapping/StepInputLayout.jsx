import { useState } from 'react'

const LAYOUTS = [
  {
    id: 'pair',
    title: 'Single file pair',
    description: 'One source file compared to one target file (current flow).',
  },
  {
    id: 'folder',
    title: 'Folder ↔ folder',
    description: 'Pick a source folder and target folder, auto-match by filename, then map columns per pair.',
  },
  {
    id: 'source-one-target-many',
    title: 'One source → many targets',
    description: 'A single source file split across multiple target files. Targets are merged before validation.',
  },
  {
    id: 'source-many-target-one',
    title: 'Many sources → one target',
    description: 'Multiple source files combined into one target file. Sources are merged before validation.',
  },
]

function formatDisplayName(fileFormat) {
  if (fileFormat === 'fixed-width') return 'Fixed-width'
  if (fileFormat === 'json') return 'JSON'
  if (fileFormat === 'zip') return 'ZIP archive'
  return 'CSV'
}

export default function StepInputLayout({ fileFormat, onNext, onBack }) {
  const [layout, setLayout] = useState('pair')

  return (
    <div style={{ animation: 'fade-in 0.2s ease' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
          Step 1 of 4 — Input layout
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 6 }}>
          How are your {formatDisplayName(fileFormat)} files organized?
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.5 }}>
          Choose whether you are validating one file pair, whole folders, or merged shards.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
        {LAYOUTS.map(item => {
          const selected = layout === item.id
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setLayout(item.id)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                gap: 8,
                padding: 16,
                borderRadius: 10,
                border: selected ? '1px solid var(--accent-border)' : '1px solid var(--border-1)',
                background: selected ? 'var(--accent-muted)' : 'var(--surface-1)',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>{item.title}</div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.45 }}>{item.description}</div>
            </button>
          )
        })}
      </div>

      <div style={{ marginTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button type="button" onClick={onBack} className="btn btn-ghost">Back</button>
        <button type="button" onClick={() => onNext(layout)} className="btn btn-primary">
          Continue
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M3 6h6M6.5 3.5L9 6l-2.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
  )
}
