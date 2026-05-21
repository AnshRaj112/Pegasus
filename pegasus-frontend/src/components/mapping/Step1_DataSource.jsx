import { useState } from 'react'

const SOURCE_TYPES = [
  {
    id: 'local',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="2" y="4" width="16" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
        <path d="M6 14v1.5h8V14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
        <rect x="6" y="7" width="8" height="4" rx="1" fill="currentColor" opacity="0.15"/>
      </svg>
    ),
    title:       'Local Device',
    description: 'Files on the server\'s local filesystem.',
    badge:       'Available',
    available:   true,
  },
  {
    id: 'cloud',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M15 12a4 4 0 00-4-4 4 4 0 00-7.5-1A3 3 0 005 13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
        <path d="M9 16l3-3 3 3M12 13v5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    title:       'Cloud Storage',
    description: 'Google Cloud Storage is available now; other providers stay blocked.',
    badge:       'Open',
    available:   true,
  },
  {
    id: 'datastore',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <ellipse cx="10" cy="6" rx="7" ry="2.5" stroke="currentColor" strokeWidth="1.4"/>
        <path d="M3 6v4c0 1.38 3.13 2.5 7 2.5S17 11.38 17 10V6" stroke="currentColor" strokeWidth="1.4"/>
        <path d="M3 10v4c0 1.38 3.13 2.5 7 2.5S17 15.38 17 14v-4" stroke="currentColor" strokeWidth="1.4"/>
      </svg>
    ),
    title:       'Data Warehouse',
    description: 'Snowflake, BigQuery, Databricks.',
    badge:       'Soon',
    available:   false,
  },
]

export default function Step1_DataSource({ onNext }) {
  const [sourceType, setSourceType] = useState(null)
  const [targetType, setTargetType] = useState(null)
  const [phase, setPhase]           = useState('source')

  function handleCardClick(type) {
    if (!type.available) return
    if (phase === 'source') { setSourceType(type.id); setPhase('target') }
    else                    { setTargetType(type.id) }
  }

  const currentPick = phase === 'source' ? sourceType : targetType

  return (
    <div style={{ animation: 'fade-in 0.2s ease' }}>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>
          Step 1 of 3
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.03em', lineHeight: 1.2, marginBottom: 6 }}>
          Where are your files?
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)', lineHeight: 1.5 }}>
          Choose the storage location for your{' '}
          <span style={{ color: phase === 'source' ? 'var(--accent)' : 'var(--text-2)', fontWeight: 500 }}>Source</span>
          {' '}file, then your{' '}
          <span style={{ color: phase === 'target' ? 'var(--accent)' : 'var(--text-2)', fontWeight: 500 }}>Target</span>
          {' '}file.
        </p>
      </div>

      {/* Phase tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
        {['source', 'target'].map(p => {
          const done   = p === 'source' ? !!sourceType : !!targetType
          const active = phase === p
          return (
            <button
              key={p}
              onClick={() => setPhase(p)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                height: 30,
                padding: '0 12px',
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
                border: active ? '1px solid var(--accent-border)' : '1px solid var(--border-2)',
                background: active ? 'var(--accent-muted)' : 'var(--surface-2)',
                color: active ? 'var(--accent)' : done ? 'var(--text-2)' : 'var(--text-3)',
                letterSpacing: '-0.01em',
              }}
            >
              {done && (
                <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                  <path d="M2 5.5l2 2 5-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
              {p === 'source' ? 'Source file' : 'Target file'}
            </button>
          )
        })}
      </div>

      {/* Type cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {SOURCE_TYPES.map(type => {
          const selected = currentPick === type.id
          return (
            <button
              key={type.id}
              onClick={() => handleCardClick(type)}
              disabled={!type.available}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                gap: 12,
                padding: '16px',
                borderRadius: 10,
                border: selected
                  ? '1px solid var(--accent-border)'
                  : '1px solid var(--border-1)',
                background: selected ? 'var(--accent-muted)' : 'var(--surface-1)',
                cursor: type.available ? 'pointer' : 'default',
                opacity: type.available ? 1 : 0.45,
                textAlign: 'left',
                transition: 'all 0.12s',
                position: 'relative',
              }}
              onMouseEnter={e => { if (type.available && !selected) e.currentTarget.style.borderColor = 'var(--border-2)' }}
              onMouseLeave={e => { if (type.available && !selected) e.currentTarget.style.borderColor = 'var(--border-1)' }}
            >
              {/* Badge */}
              <span style={{
                position: 'absolute', top: 10, right: 10,
                fontSize: 10, fontWeight: 600, letterSpacing: '0.04em',
                padding: '2px 6px', borderRadius: 4,
                background: type.available ? 'var(--success-muted)' : 'var(--surface-3)',
                color: type.available ? 'var(--success)' : 'var(--text-4)',
                border: type.available ? '1px solid rgba(34,197,94,0.2)' : '1px solid var(--border-1)',
              }}>
                {type.badge}
              </span>

              {/* Icon */}
              <div style={{
                width: 36, height: 36,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                borderRadius: 8,
                background: selected ? 'var(--accent)' : 'var(--surface-3)',
                color: selected ? '#fff' : 'var(--text-2)',
                border: selected ? 'none' : '1px solid var(--border-2)',
                flexShrink: 0,
              }}>
                {type.icon}
              </div>

              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)', letterSpacing: '-0.01em', marginBottom: 3 }}>
                  {type.title}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.4 }}>
                  {type.description}
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Confirm bar */}
      {sourceType && targetType && (
        <div style={{
          marginTop: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          padding: '12px 16px',
          borderRadius: 10,
          background: 'var(--surface-2)',
          border: '1px solid var(--border-2)',
          animation: 'fade-in 0.15s ease',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-2)' }}>
            <span style={{ color: 'var(--text-1)', fontWeight: 500 }}>
              {SOURCE_TYPES.find(t => t.id === sourceType)?.title}
            </span>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ color: 'var(--text-4)' }}>
              <path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span style={{ color: 'var(--text-1)', fontWeight: 500 }}>
              {SOURCE_TYPES.find(t => t.id === targetType)?.title}
            </span>
          </div>
          <button
            onClick={() => onNext(sourceType, targetType)}
            className="btn btn-primary"
            style={{ gap: 6 }}
          >
            Continue
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M3 6h6M6.5 3.5L9 6l-2.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}
