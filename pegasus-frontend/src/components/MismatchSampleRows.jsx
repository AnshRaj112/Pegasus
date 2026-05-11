function RecordCard({ title, record, variant }) {
  if (!record || typeof record !== 'object') return null
  const entries = Object.entries(record)
  return (
    <div
      className={`validation-record validation-record--${variant}`}
      role="group"
      aria-label={title}
    >
      <div className="validation-record-title">{title}</div>
      <dl className="validation-record-dl">
        {entries.map(([key, val]) => (
          <div key={key} className="validation-record-pair">
            <dt>{key}</dt>
            <dd>{val === null || val === undefined ? '—' : String(val)}</dd>
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
          <tr key={`${key}-main`}>
            <td>{row.uid}</td>
            <td>
              <code className="validation-type-pill">{row.mismatch_type}</code>
            </td>
            <td>{row.column_name ?? '—'}</td>
            <td
              className={
                isExtra
                  ? 'validation-cell-muted'
                  : 'validation-cell-expected'
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
                  ? 'validation-cell-muted'
                  : 'validation-cell-actual'
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
            <tr key={`${key}-detail`} className="validation-detail-row">
              <td colSpan={5}>
                <div className="validation-detail-hint">
                  {isMissing &&
                    'This row exists in the source file but not in the target — expected values:'}
                  {isExtra &&
                    'This row exists in the target file but not in the source — unexpected values:'}
                  {isValue &&
                    'Full row context (expected vs actual across all compared columns):'}
                </div>
                <div className="validation-detail-grid">
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