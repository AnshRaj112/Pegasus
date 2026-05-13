import React, { useEffect, useState } from 'react'

const mockResults = {
  mismatches: 5,
  missing: 3,
  extra: 2,
  details: [
    { line: 1, type: 'mismatch', sourceValue: 'John Doe', targetValue: 'Jon Doe', description: 'Name spelling difference' },
    { line: 2, type: 'missing', sourceValue: 'Email: john@example.com', targetValue: 'N/A', description: 'Email field missing in target' },
    { line: 3, type: 'extra', sourceValue: 'N/A', targetValue: 'Phone: 1234567890', description: 'Extra field in target file' },
    { line: 4, type: 'mismatch', sourceValue: '25', targetValue: '26', description: 'Age mismatch' },
    { line: 5, type: 'missing', sourceValue: 'Address: 123 Main St', targetValue: 'N/A', description: 'Address not in target' },
    { line: 6, type: 'extra', sourceValue: 'N/A', targetValue: 'Department: IT', description: 'Department added in target' },
    { line: 7, type: 'mismatch', sourceValue: 'Active', targetValue: 'Inactive', description: 'Status changed' },
    { line: 8, type: 'missing', sourceValue: 'Salary: $50000', targetValue: 'N/A', description: 'Salary removed' },
    { line: 9, type: 'extra', sourceValue: 'N/A', targetValue: 'LastUpdated: 2024-01-15', description: 'Timestamp added' },
    { line: 10, type: 'mismatch', sourceValue: 'New York', targetValue: 'Los Angeles', description: 'City changed' },
  ],
}

const sectionCard = 'rounded-2xl border border-[#F1F1F1] bg-white shadow-[0_12px_40px_rgba(235,76,76,0.10)]'
const columnHeader = 'px-5 py-4 text-sm font-semibold tracking-wide text-[#FFFDEF]'
const tagBase = 'inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]'

export default function UI() {
  const [isLoading, setIsLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [showDetailed, setShowDetailed] = useState(false)

  useEffect(() => {
    setResults(mockResults)
  }, [])

  const handleCompare = () => {
    setIsLoading(true)
    setShowDetailed(false)

    setTimeout(() => {
      setResults(mockResults)
      setIsLoading(false)
    }, 1500)
  }

  const getDetailsByType = (type) => results?.details.filter((detail) => detail.type === type) ?? []

  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,#FFFDEF_0%,#F1F1F1_100%)] px-4 py-6 text-slate-800 sm:px-6 lg:px-8">
        <div>
            <img
            src="https://www.onixnet.com/wp-content/uploads/2024/12/Onix-Logo.svg"
            alt="Logo"
            className="h-16 w-16 shrink-0 object-contain sm:h-20 sm:w-20 lg:h-24 lg:w-24"
          />
        </div>
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 flex items-center gap-6 text-[#EB4C4C]">
          
          <div>
            <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">Pegasus</h1>
            
          </div>
        </header>

        <section className={`${sectionCard} mb-8 border-l-4 border-l-[#EB4C4C] p-6 sm:p-8`}>
          <p className="mb-5 text-center text-sm font-medium text-slate-600 sm:text-base">
            Dummy data is used for demonstrating the comparison simulation.
          </p>
          <button
            type="button"
            onClick={handleCompare}
            disabled={isLoading}
            className="w-full rounded-xl bg-[#EB4C4C] px-5 py-4 text-base font-semibold text-[#FFFDEF] shadow-[0_12px_30px_rgba(235,76,76,0.28)] transition duration-200 hover:-translate-y-0.5 hover:bg-[#d83e3e] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? 'Comparing...' : 'Simulate Comparison'}
          </button>
        </section>

        {isLoading && (
          <section className={`${sectionCard} mb-8 border-l-4 border-l-[#EB4C4C] p-8 text-center`}>
            <div className="mb-4 flex items-center justify-center gap-4" role="status" aria-live="polite">
              <div className="h-12 w-12 animate-spin rounded-full border-[5px] border-[#F1F1F1] border-t-[#EB4C4C]" />
            </div>
            <p className="text-lg font-medium text-[#EB4C4C]">Analyzing files...</p>
          </section>
        )}

        {results && !isLoading && (
          <div className="space-y-8">
            <section className={`${sectionCard} border-l-4 border-l-[#EB4C4C] p-6 sm:p-8`}>
              <div className="mb-8 flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-bold text-[#EB4C4C]">Summary</h2>
                  <p className="mt-1 text-sm text-slate-500">High-level counts from the latest comparison.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowDetailed((value) => !value)}
                  className="rounded-lg border border-[#EB4C4C] px-4 py-2 text-sm font-semibold text-[#EB4C4C] transition hover:bg-[#FFFDEF]"
                >
                  {showDetailed ? 'Hide Detailed Report' : 'View Detailed Report'}
                </button>
              </div>

              <div className="grid gap-5 md:grid-cols-3">
                <div className="rounded-2xl bg-[#EB4C4C] p-6 text-[#FFFDEF] shadow-[0_14px_32px_rgba(235,76,76,0.22)]">
                  <div className="text-5xl font-black leading-none">{results.mismatches}</div>
                  <div className="mt-3 text-sm font-medium uppercase tracking-[0.2em]">Mismatches</div>
                </div>
                <div className="rounded-2xl bg-[#FF7070] p-6 text-[#FFFDEF] shadow-[0_14px_32px_rgba(235,76,76,0.18)]">
                  <div className="text-5xl font-black leading-none">{results.missing}</div>
                  <div className="mt-3 text-sm font-medium uppercase tracking-[0.2em]">Missing Entries</div>
                </div>
                <div className="rounded-2xl bg-[#FFA6A6] p-6 text-[#FFFDEF] shadow-[0_14px_32px_rgba(235,76,76,0.18)]">
                  <div className="text-5xl font-black leading-none">{results.extra}</div>
                  <div className="mt-3 text-sm font-medium uppercase tracking-[0.2em]">Extra Entries</div>
                </div>
              </div>
            </section>

            {showDetailed && (
              <section className={`${sectionCard} border-l-4 border-l-[#EB4C4C] p-6 sm:p-8`}>
                <div className="mb-6">
                  <h2 className="text-2xl font-bold text-[#EB4C4C]">Detailed Analysis</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Line-by-line review of mismatches, missing entries, and extras.
                  </p>
                </div>

                <div className="grid gap-5 xl:grid-cols-3">
                  {[
                    { key: 'mismatch', title: 'Mismatches', count: getDetailsByType('mismatch').length, headerClass: 'bg-[#EB4C4C]' },
                    { key: 'missing', title: 'Missing Entries', count: getDetailsByType('missing').length, headerClass: 'bg-[#FF7070]' },
                    { key: 'extra', title: 'Extra Entries', count: getDetailsByType('extra').length, headerClass: 'bg-[#FFA6A6]' },
                  ].map((column) => (
                    <article key={column.key} className="overflow-hidden rounded-2xl border border-[#F1F1F1] bg-[#F1F1F1]">
                      <div className={`${columnHeader} ${column.headerClass}`}>
                        <h3 className="text-lg font-bold">{column.title} ({column.count})</h3>
                      </div>

                      <div className="max-h-[34rem] space-y-4 overflow-y-auto p-4">
                        {getDetailsByType(column.key).map((detail) => (
                          <div key={`${column.key}-${detail.line}`} className="rounded-xl border-l-4 border-l-[#EB4C4C] bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
                            <div className="mb-3 flex items-center justify-between gap-3">
                              <span className={tagBase + ' bg-[#FFFDEF] text-[#EB4C4C]'}>Line {detail.line}</span>
                              <span className={tagBase + ' bg-[#F1F1F1] text-slate-600'}>{detail.type}</span>
                            </div>

                            <div className="space-y-3 text-sm">
                              <div>
                                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Source</p>
                                <p className="mt-1 rounded-lg bg-[#F1F1F1] px-3 py-2 text-slate-800">{detail.sourceValue}</p>
                              </div>
                              <div>
                                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Target</p>
                                <p className="mt-1 rounded-lg bg-[#F1F1F1] px-3 py-2 text-slate-800">{detail.targetValue}</p>
                              </div>
                              <p className="border-t border-[#F1F1F1] pt-3 text-xs italic text-slate-500">{detail.description}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
