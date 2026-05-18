import React, { useState, useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Mismatched from './Mismatched'
import Extra from './Extra'
import Missing from './Missing'

export default function DetailedReport() {
  const location = useLocation()
  const navigate = useNavigate()
  const result = location?.state?.result ?? null
  const [filterUid, setFilterUid] = useState('')

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

  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,#FFFDEF_0%,#F1F1F1_100%)] px-4 py-6 text-slate-800 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 flex items-center justify-between">
          <h2 className="text-3xl font-bold">Detailed Report</h2>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(-1)}
              className="rounded-lg bg-white px-4 py-2 text-sm font-medium border border-slate-200 hover:bg-slate-50"
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
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Total Entries</p>
                <p className="mt-2 text-3xl font-bold text-slate-900">{totalAll}</p>
              </div>
              <div className="rounded-xl bg-white border border-slate-200 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Mismatched</p>
                <p className="mt-2 text-3xl font-bold text-orange-600">{totalMismatched}</p>
              </div>
              <div className="rounded-xl bg-white border border-slate-200 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Missing in Target</p>
                <p className="mt-2 text-3xl font-bold text-amber-600">{totalMissing}</p>
              </div>
              <div className="rounded-xl bg-white border border-slate-200 p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Extra in Target</p>
                <p className="mt-2 text-3xl font-bold text-blue-600">{totalExtra}</p>
              </div>
            </div>

            {/* Filter Section */}
            <div className="mb-6 rounded-xl bg-white border border-slate-200 p-4 shadow-sm">
              <label className="block text-sm font-semibold text-slate-700 mb-2">Filter by UID</label>
              <input
                type="text"
                placeholder="Enter UID to search..."
                value={filterUid}
                onChange={(e) => setFilterUid(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm focus:border-orange-500 focus:outline-none focus:ring-2 focus:ring-orange-500/20"
              />
              {filterUid && (
                <p className="mt-2 text-sm text-slate-600">
                  Showing {totalMismatched + totalExtra + totalMissing} results for UID containing "{filterUid}"
                </p>
              )}
            </div>

            {/* Report Sections */}
            <main className="space-y-8">
              <section>
                <Mismatched samples={valueMismatch} />
              </section>

              <section>
                <Extra samples={extra} />
              </section>

              <section>
                <Missing samples={missing} />
              </section>
            </main>
          </>
        )}
      </div>
    </div>
  )
}
