import React, { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ReportSection from './ReportSection'

export default function DetailedReport() {
  const location = useLocation()
  const navigate = useNavigate()
  const result = location?.state?.result ?? null
  const [filterUid, setFilterUid] = useState('')
  const [activeSection, setActiveSection] = useState('mismatched')
  const samples = result?.mismatch_samples ?? []
  
  const filteredSamples = useMemo(() => {
    if (!filterUid.trim()) return samples
    return samples.filter((s) => 
      s.uid?.toLowerCase().includes(filterUid.toLowerCase())
    )
  }, [samples, filterUid])

  const valueMismatch = filteredSamples.filter((s) => s.mismatch_type === 'value_mismatch')
  const extra = filteredSamples.filter((s) => s.mismatch_type === 'extra_in_target')
  const missing = filteredSamples.filter((s) => s.mismatch_type === 'missing_in_target')
  const totalMismatched = samples.filter((s) => s.mismatch_type === 'value_mismatch').length
  const totalExtra = samples.filter((s) => s.mismatch_type === 'extra_in_target').length
  const totalMissing = samples.filter((s) => s.mismatch_type === 'missing_in_target').length
  const totalAll = totalMismatched + totalExtra + totalMissing
  const visibleTotalMismatched = valueMismatch.length
  const visibleTotalExtra = extra.length
  const visibleTotalMissing = missing.length
  const visibleTotalAll = visibleTotalMismatched + visibleTotalExtra + visibleTotalMissing

  const sections = [
    {
      key: 'mismatched',
      label: 'Mismatched',
      count: valueMismatch.length,
      tone: 'bg-amber-50 text-amber-900 ring-amber-200',
      activeTone: 'bg-amber-500 text-white shadow-lg shadow-amber-200',
    },
    {
      key: 'missing_in_target',
      label: 'Missing',
      count: missing.length,
      tone: 'bg-rose-50 text-rose-900 ring-rose-200',
      activeTone: 'bg-rose-500 text-white shadow-lg shadow-rose-200',
    },
    {
      key: 'extra_in_target',
      label: 'Extra',
      count: extra.length,
      tone: 'bg-sky-50 text-sky-900 ring-sky-200',
      activeTone: 'bg-sky-500 text-white shadow-lg shadow-sky-200',
    },
  ]

  const activeSamples =
    activeSection === 'missing_in_target'
      ? missing
      : activeSection === 'extra_in_target'
        ? extra
        : valueMismatch

  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,#FFFDEF_0%,#F1F1F1_100%)] px-4 py-6 text-slate-800 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 rounded-3xl border border-white/70 bg-white/80 p-6 shadow-sm backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">Validation output</p>
              <h2 className="mt-2 text-3xl font-black text-slate-900">Detailed Report</h2>
              <p className="mt-2 max-w-3xl text-sm text-slate-600">
                Review mismatched, missing, and extra records in separate sections with unified cards and page-by-page navigation.
              </p>
            </div>
            <button
              onClick={() => navigate(-1)}
              className="w-fit rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
            >
              Back
            </button>
          </div>
        </header>

        {!result ? (
          <div className="rounded-xl bg-white p-6">No report data received. Return to the validation panel and click View Detailed Report.</div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl bg-white border border-slate-200 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Total Wrong Entries</p>
                <p className="mt-2 text-3xl font-bold text-slate-900">{filterUid ? visibleTotalAll : totalAll}</p>
              </div>
              <div className="rounded-xl bg-white border border-slate-200 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Mismatched</p>
                <p className="mt-2 text-3xl font-bold text-orange-600">{filterUid ? visibleTotalMismatched : totalMismatched}</p>
              </div>
              <div className="rounded-xl bg-white border border-slate-200 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Missing in Target</p>
                <p className="mt-2 text-3xl font-bold text-amber-600">{filterUid ? visibleTotalMissing : totalMissing}</p>
              </div>
              <div className="rounded-xl bg-white border border-slate-200 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Extra in Target</p>
                <p className="mt-2 text-3xl font-bold text-blue-600">{filterUid ? visibleTotalExtra : totalExtra}</p>
              </div>
            </div>

            {/* Filter Section */}
            <div className="mb-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <label className="mb-2 block text-sm font-semibold text-slate-700">Filter by UID</label>
              <input
                type="text"
                placeholder="Enter UID to search..."
                value={filterUid}
                onChange={(e) => setFilterUid(e.target.value)}
                className="w-full rounded-2xl border border-slate-300 px-4 py-3 text-sm focus:border-orange-500 focus:outline-none focus:ring-2 focus:ring-orange-500/20"
              />
              {filterUid && (
                <p className="mt-2 text-sm text-slate-600">
                  Showing {filteredSamples.length} results for UID containing "{filterUid}"
                </p>
              )}
            </div>

            <div className="mb-6 grid gap-3 md:grid-cols-3">
              {sections.map((section) => {
                const isActive = activeSection === section.key
                return (
                  <button
                    key={section.key}
                    type="button"
                    onClick={() => setActiveSection(section.key)}
                    className={`rounded-3xl border px-4 py-4 text-left transition ${isActive ? section.activeTone : `${section.tone} border-transparent hover:bg-white`}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-semibold uppercase tracking-[0.24em]">{section.label}</span>
                      <span className="rounded-full bg-white/70 px-3 py-1 text-sm font-black text-slate-900 shadow-sm">
                        {section.count}
                      </span>
                    </div>
                    <p className={`mt-3 text-sm ${isActive ? 'text-white/90' : 'text-slate-600'}`}>
                      {section.key === 'mismatched'
                        ? 'Rows with changed values between source and target.'
                        : section.key === 'missing_in_target'
                          ? 'Rows present only in the source file.'
                          : 'Rows present only in the target file.'}
                    </p>
                  </button>
                )
              })}
            </div>

            <main>
              <ReportSection type={activeSection} samples={activeSamples} />
            </main>
          </>
        )}
      </div>
    </div>
  )
}