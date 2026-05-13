import { ValidationPanel } from './components/ValidationPanel'

function App() {
  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,#FFFDEF_0%,#F1F1F1_100%)] px-4 py-6 text-slate-800 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 flex items-center gap-6 text-[#EB4C4C]">
          <img
            src="https://www.onixnet.com/wp-content/uploads/2024/12/Onix-Logo.svg"
            alt="Onix logo"
            className="h-16 w-16 shrink-0 object-contain sm:h-20 sm:w-20 lg:h-24 lg:w-24"
          />
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">Pegasus</h1>
        </header>

        <main>
        <ValidationPanel />
        </main>
      </div>
    </div>
  )
}

export default App