import { useState } from 'react'
import MappingWizard  from './components/mapping/MappingWizard'
import History         from './components/History'
import Dashboard       from './components/Dashboard'
import { LayoutDashboard, Compass, History as HistoryIcon, ShieldCheck } from 'lucide-react'

function App() {
  const [activeSection, setActiveSection] = useState('dashboard')
  const [initialMappingData, setInitialMappingData] = useState(null)

  const handleLoadMapping = (data) => {
    setInitialMappingData(data)
    setActiveSection('mapping')
  }

  const handleSectionChange = (section) => {
    if (section !== 'mapping') {
      setInitialMappingData(null)
    }
    setActiveSection(section)
  }

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--surface-0)' }}>
      {/* Sidebar Navigation */}
      <aside style={{
        width: '260px',
        flexShrink: 0,
        background: 'var(--surface-1)',
        borderRight: '1px solid var(--border-1)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}>
        {/* Brand Header */}
        <div style={{
          padding: '24px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          borderBottom: '1px solid var(--border-1)'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 36,
            height: 36,
            borderRadius: 8,
            background: 'var(--accent-muted)',
            color: 'var(--accent)',
          }}>
            <ShieldCheck size={22} />
          </div>
          <span style={{
            fontSize: 20,
            fontWeight: 800,
            color: 'var(--text-1)',
            letterSpacing: '-0.03em',
          }}>
            Pegasus
          </span>
          <img
            src="/Pegasus.png"
            alt="Pegasus"
            style={{ height: 32, width: 32, objectFit: 'contain', borderRadius: 4, marginLeft: 'auto' }}
          />
        </div>

        {/* Navigation Section */}
        <nav style={{
          flex: 1,
          padding: '24px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}>
          {[
            { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
            { id: 'mapping', label: 'Mapping', icon: Compass },
            { id: 'history', label: 'History', icon: HistoryIcon },
          ].map(({ id, label, icon: Icon }) => {
            const active = activeSection === id
            return (
              <button
                key={id}
                onClick={() => handleSectionChange(id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: active ? 600 : 500,
                  color: active ? 'var(--accent)' : 'var(--text-2)',
                  background: active ? 'var(--accent-muted)' : 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  textAlign: 'left',
                }}
                onMouseEnter={e => {
                  if (!active) {
                    e.currentTarget.style.color = 'var(--text-1)'
                    e.currentTarget.style.background = 'var(--surface-2)'
                    e.currentTarget.style.transform = 'translateX(4px)'
                  }
                }}
                onMouseLeave={e => {
                  if (!active) {
                    e.currentTarget.style.color = 'var(--text-2)'
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.transform = 'none'
                  }
                }}
              >
                <Icon size={18} style={{
                  color: active ? 'var(--accent)' : 'var(--text-3)',
                  transition: 'color 0.2s'
                }} />
                {label}
              </button>
            )
          })}
        </nav>

        {/* User Profile */}
        <div style={{
          padding: '20px',
          borderTop: '1px solid var(--border-1)',
          background: 'var(--surface-2)',
          display: 'flex',
          alignItems: 'center',
          gap: 12
        }}>
          <img
            src="./photo.jpg"
            alt="Profile"
            style={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              objectFit: 'cover',
              border: '2px solid var(--border-2)',
            }}
          />
          <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            <span style={{
              fontSize: 14,
              fontWeight: 700,
              color: 'var(--text-1)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
              Super User
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 500 }}>
              Admin
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main style={{
        flex: 1,
        height: '100%',
        overflowY: 'auto',
        padding: '32px 40px 48px',
        background: 'var(--surface-0)',
      }}>
        {activeSection === 'mapping' && (
          <MappingWizard
            initialMappingData={initialMappingData}
            onResetInitialData={() => setInitialMappingData(null)}
          />
        )}
        {activeSection === 'history' && <History onLoadMapping={handleLoadMapping} />}
        {activeSection === 'dashboard' && <Dashboard />}
      </main>
    </div>
  )
}

export default App