import { useState } from 'react'
import Header         from './components/Header'
import MappingWizard  from './components/mapping/MappingWizard'
import History         from './components/History'

function App() {
  const [activeSection, setActiveSection] = useState('mapping')
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
    <div style={{ minHeight: '100vh', background: 'var(--surface-0)' }}>
      <Header activeSection={activeSection} onSectionChange={handleSectionChange} />

      <main style={{ maxWidth: 1080, margin: '0 auto', padding: '32px 24px 64px' }}>
        {activeSection === 'mapping' && (
          <MappingWizard
            initialMappingData={initialMappingData}
            onResetInitialData={() => setInitialMappingData(null)}
          />
        )}
        {activeSection === 'history' && <History onLoadMapping={handleLoadMapping} />}
      </main>
    </div>
  )
}

export default App