import { ValidationPanel } from './components/ValidationPanel'
import './App.css'

function App() {
  return (
    <>
      <header className="app-header mt-5">
        <h1 className='pb-8'>Pegasus</h1>
        {/* <p className="app-tagline">CSV validation</p> */}
      </header>

      <main className="app-main mt-7">
        <ValidationPanel />
      </main>
    </>
  )
}

export default App