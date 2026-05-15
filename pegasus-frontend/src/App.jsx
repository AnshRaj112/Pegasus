import { useState } from 'react'
import Header from './components/Header'
import { ValidationPanel } from './components/ValidationPanel'
import History from './components/History'

function App() {
  const [activeSection, setActiveSection] = useState('validation')

  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,#FFFDEF_0%,#F1F1F1_100%)] text-slate-800">
      <Header activeSection={activeSection} onSectionChange={setActiveSection} />
      
      <div className="px-4 py-8 sm:px-6 lg:px-8 mt-6">
        <div className="mx-auto max-w-7xl">
          <main>
            {activeSection === 'validation' && <ValidationPanel />}
            {activeSection === 'history' && <History />}
          </main>
        </div>
      </div>
    </div>
  )
}

export default App