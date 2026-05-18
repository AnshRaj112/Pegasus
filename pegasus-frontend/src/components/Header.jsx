const NAV_ITEMS = [
  { id: 'mapping',  label: 'Mapping'  },
  { id: 'history',  label: 'History'  },
]

export default function Header({ activeSection, onSectionChange }) {
  return (
    <header style={{
      position: 'sticky',
      top: 0,
      zIndex: 50,
      background: 'var(--surface-0)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      borderBottom: '1px solid var(--border-1)',
    }}>
      <div style={{ maxWidth: 1080, margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'flex', height: 52, alignItems: 'center', gap: 32 }}>

          {/* Wordmark */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>
            <img
              src="/Pegasus.png"
              alt="Pegasus"
              style={{ height: 26, width: 26, objectFit: 'contain', borderRadius: 6 }}
            />
            <span style={{
              fontSize: 15,
              fontWeight: 700,
              color: 'var(--text-1)',
              letterSpacing: '-0.02em',
            }}>
              Pegasus
            </span>
          </div>

          {/* Divider */}
          <div style={{ width: 1, height: 18, background: 'var(--border-2)', flexShrink: 0 }} />

          {/* Navigation tabs */}
          <nav style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {NAV_ITEMS.map(({ id, label }) => {
              const active = activeSection === id
              return (
                <button
                  key={id}
                  onClick={() => onSectionChange(id)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    height: 28,
                    padding: '0 10px',
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: active ? 500 : 400,
                    color: active ? 'var(--text-1)' : 'var(--text-3)',
                    background: active ? 'var(--surface-3)' : 'transparent',
                    border: active ? '1px solid var(--border-2)' : '1px solid transparent',
                    cursor: 'pointer',
                    transition: 'all 0.12s',
                    letterSpacing: '-0.01em',
                  }}
                  onMouseEnter={e => {
                    if (!active) { e.currentTarget.style.color = 'var(--text-2)'; e.currentTarget.style.background = 'var(--surface-2)' }
                  }}
                  onMouseLeave={e => {
                    if (!active) { e.currentTarget.style.color = 'var(--text-3)'; e.currentTarget.style.background = 'transparent' }
                  }}
                >
                  {label}
                </button>
              )
            })}
          </nav>

          {/* Spacer + right slot */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{
              fontSize: 11,
              fontWeight: 500,
              color: 'var(--text-4)',
              letterSpacing: '0.04em',
            }}>
              {/* v0.1.0-alpha */}
            </span>
          </div>

        </div>
      </div>
    </header>
  )
}
