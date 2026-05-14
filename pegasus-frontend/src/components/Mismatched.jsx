import React, { useState, useMemo } from 'react'
import { MismatchSampleRows } from './MismatchSampleRows'

export default function Mismatched({ samples = [] }) {
  const options = [10, 20, 50, 100, 1000, 'all']
  const [pageSize, setPageSize] = useState(10)

  const visible = useMemo(() => {
    if (pageSize === 'all') return samples
    return samples.slice(0, Number(pageSize))
  }, [samples, pageSize])

  return (
    <div className="rounded-2xl border border-[#F1F1F1] bg-white p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-bold">Mismatched values</h3>
        <div className="flex items-center gap-3">
          <label className="text-sm text-slate-600">Show</label>
          <select
            value={pageSize}
            onChange={(e) => setPageSize(e.target.value === 'all' ? 'all' : Number(e.target.value))}
            className="rounded-md border px-2 py-1"
          >
            {options.map((o) => (
              <option key={String(o)} value={o}>
                {o === 'all' ? 'All' : o}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-[#F1F1F1]">
        <table className="min-w-full border-collapse text-left text-sm">
          <thead>
            <tr className="bg-[#FFFDEF] text-xs uppercase tracking-wide text-slate-600">
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
