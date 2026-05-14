import React from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Mismatched from './Mismatched'
import Extra from './Extra'
import Missing from './Missing'

export default function DetailedReport() {
  const location = useLocation()
  const navigate = useNavigate()
  const result = location?.state?.result ?? null

  const samples = result?.mismatch_samples ?? []
  const valueMismatch = samples.filter((s) => s.mismatch_type === 'value_mismatch')
  const extra = samples.filter((s) => s.mismatch_type === 'extra_in_target')
  const missing = samples.filter((s) => s.mismatch_type === 'missing_in_target')

  return (
    <div className="min-h-screen bg-[linear-gradient(135deg,#FFFDEF_0%,#F1F1F1_100%)] px-4 py-6 text-slate-800 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold">Detailed Report</h2>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(-1)}
              className="rounded-lg bg-white px-3 py-2 text-sm font-medium border"
            >
              Back
            </button>
          </div>
        </header>

        {!result ? (
          <div className="rounded-xl bg-white p-6">No report data received. Return to the validation panel and click View Detailed Report.</div>
        ) : (
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
        )}
      </div>
    </div>
  )
}
