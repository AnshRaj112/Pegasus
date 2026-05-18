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
      paddingTop: 8,
      paddingBottom: 8,
    }}>
      <div style={{ position: 'relative', width: '100%', padding: '0 24px' }}>
        {/* Left: large logo + name (absolute to place at extreme left) */}
        <div style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <img
            src="/Pegasus.png"
            alt="Pegasus"
            style={{ height: 44, width: 44, objectFit: 'contain', borderRadius: 8, transform: 'translateY(-6px)' }}
          />
          <span style={{
            fontSize: 18,
            fontWeight: 700,
            color: 'var(--text-1)',
            letterSpacing: '-0.02em',
            marginLeft: 2,
          }}>
            Pegasus
          </span>
        </div>

        <div style={{ display: 'flex', height: 96, alignItems: 'center', gap: 32, paddingLeft: 160 }}>
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
                    height: 36,
                    padding: '0 14px',
                    borderRadius: 8,
                    fontSize: 15,
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

        {/* Right: profile area */}
        <div style={{ position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <img src="/profile.png" alt="Profile" style={{ width: 48, height: 48, borderRadius: 9999, objectFit: 'cover', border: '1px solid var(--border-2)' }} />
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-1)' }}>Super User</span>
              <span style={{ fontSize: 12, color: 'var(--text-3)' }}>Admin</span>
            </div>
          </div>
        </div>

      </div>
    </header>
  )
}
