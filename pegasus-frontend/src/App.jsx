import { useState } from 'react'
import Header         from './components/Header'
import MappingWizard  from './components/mapping/MappingWizard'
import History         from './components/History'

function App() {
  const [activeSection, setActiveSection] = useState('mapping')

  return (
    <div style={{ minHeight: '100vh', background: 'var(--surface-0)' }}>
      <Header activeSection={activeSection} onSectionChange={setActiveSection} />

      <main style={{ maxWidth: 1080, margin: '0 auto', padding: '32px 24px 64px' }}>
        {activeSection === 'mapping' && <MappingWizard />}
        {activeSection === 'history' && <History />}
      </main>
    </div>
  )
}

export default App