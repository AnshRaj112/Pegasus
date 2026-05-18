import React, { useState, useMemo } from 'react'
import { MismatchSampleRows } from './MismatchSampleRows'

export function Extra({ samples = [] }) {
  const options = [10, 20, 50, 100, 1000, 'all']
  const [pageSize, setPageSize] = useState(10)

  const visible = useMemo(() => {
    if (pageSize === 'all') return samples
    return samples.slice(0, Number(pageSize))
  }, [samples, pageSize])

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-900">Extra in target</h3>
          <p className="mt-1 text-sm text-slate-600">Total: <span className="font-semibold text-slate-900">{samples.length}</span></p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-slate-700 font-medium">Show</label>
          <select
            value={pageSize}
            onChange={(e) => setPageSize(e.target.value === 'all' ? 'all' : Number(e.target.value))}
            className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-900 focus:border-orange-500 focus:outline-none focus:ring-2 focus:ring-orange-500/20"
          >
            {options.map((o) => (
              <option key={String(o)} value={o}>
                {o === 'all' ? 'All' : o}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="min-w-full border-collapse text-left text-sm text-slate-900">
          <thead>
            <tr className="bg-slate-50 text-xs uppercase tracking-wide text-slate-700 border-b border-slate-200">
              <th className="px-3 py-2 font-semibold">UID</th>
              <th className="px-3 py-2 font-semibold">Type</th>
              <th className="px-3 py-2 font-semibold">Column</th>
              <th className="px-3 py-2 font-semibold">Expected (source)</th>
              <th className="px-3 py-2 font-semibold">Actual (target)</th>
            </tr>
          </thead>
          <MismatchSampleRows samples={visible} />
        </table>
      </div>
    </div>
  )
}

export default Extra
