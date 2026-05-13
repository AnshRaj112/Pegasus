function RecordCard({ title, record, variant }) {
  if (!record || typeof record !== 'object') return null
  const entries = Object.entries(record)
  const containerClass =
    variant === 'source'
      ? 'rounded-lg border border-emerald-300 border-l-4 border-l-emerald-500 bg-emerald-50 p-3 text-left'
      : 'rounded-lg border border-rose-300 border-l-4 border-l-rose-500 bg-rose-50 p-3 text-left'
  return (
    <div className={containerClass} role="group" aria-label={title}>
      <div className="mb-2 text-xs font-semibold text-slate-700">{title}</div>
      <dl className="space-y-1">
        {entries.map(([key, val]) => (
          <div key={key} className="grid grid-cols-[minmax(5rem,28%)_1fr] items-baseline gap-x-2 text-xs">
            <dt className="font-medium text-slate-600">{key}</dt>
            <dd className="break-words font-mono text-slate-900">{val === null || val === undefined ? '—' : String(val)}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

export function MismatchSampleRows({ samples }) {
  if (!samples?.length) return null

  return (
    <tbody>
      {samples.flatMap((row, i) => {
        const key = `${row.uid}-${row.mismatch_type}-${i}`
        const detail = row.row_detail
        const isMissing = row.mismatch_type === 'missing_in_target'
        const isExtra = row.mismatch_type === 'extra_in_target'
        const isValue = row.mismatch_type === 'value_mismatch'

        const mainRow = (
          <tr key={`${key}-main`} className="border-b border-[#F1F1F1] text-slate-700">
            <td className="px-3 py-2 font-mono text-xs">{row.uid}</td>
            <td className="px-3 py-2">
              <code className="inline-flex rounded-full bg-[#FFFDEF] px-2 py-1 text-xs font-semibold text-[#EB4C4C]">
                {row.mismatch_type}
              </code>
            </td>
            <td className="px-3 py-2 text-xs">{row.column_name ?? '—'}</td>
            <td
              className={
                isExtra
                  ? 'px-3 py-2 font-mono text-xs text-slate-400'
                  : 'px-3 py-2 font-mono text-xs font-medium text-emerald-800 bg-emerald-100/70'
              }
            >
              {isMissing
                ? '—'
                : row.source_value != null && row.source_value !== ''
                  ? row.source_value
                  : '—'}
            </td>
            <td
              className={
                isMissing
                  ? 'px-3 py-2 font-mono text-xs text-slate-400'
                  : 'px-3 py-2 font-mono text-xs font-medium text-rose-800 bg-rose-100/70'
              }
            >
              {isExtra
                ? '—'
                : row.target_value != null && row.target_value !== ''
                  ? row.target_value
                  : '—'}
            </td>
          </tr>
        )

        const detailRow =
          detail &&
          (detail.source_record || detail.target_record) ? (
            <tr key={`${key}-detail`} className="border-b border-[#F1F1F1] bg-[#FFFDEF]">
              <td colSpan={5} className="px-3 py-3 align-top">
                <div className="mb-3 text-xs text-slate-600">
                  {isMissing &&
                    'This row exists in the source file but not in the target — expected values:'}
                  {isExtra &&
                    'This row exists in the target file but not in the source — unexpected values:'}
                  {isValue &&
                    'Full row context (expected vs actual across all compared columns):'}
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {detail.source_record ? (
                    <RecordCard
                      variant="source"
                      title="Source (expected) — reference"
                      record={detail.source_record}
                    />
                  ) : null}
                  {detail.target_record ? (
                    <RecordCard
                      variant="target"
                      title="Target (actual)"
                      record={detail.target_record}
                    />
                  ) : null}
                </div>
              </td>
            </tr>
          ) : null

        return detailRow ? [mainRow, detailRow] : [mainRow]
      })}
    </tbody>
  )
}