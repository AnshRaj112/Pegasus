import { Card, Col, Divider, Row, Space, Table, Tag, Typography } from 'antd'

/**
 * Renders a side-by-side comparison of source and target row details.
 * Used for "Full detail" view to show all columns with differences highlighted.
 */
function columnValueCell(value) {
  const v =
    value != null && value !== ''
      ? typeof value === 'string'
        ? value
        : String(value)
      : '—'
  return (
    <Typography.Text
      style={{ fontFamily: 'ui-monospace, monospace', fontSize: 13 }}
      ellipsis={{ tooltip: v }}
    >
      {v}
    </Typography.Text>
  )
}

function mismatchTag(type) {
  if (type === 'missing_in_target') return <Tag color="orange">{type}</Tag>
  if (type === 'extra_in_target') return <Tag color="purple">{type}</Tag>
  if (type === 'value_mismatch') return <Tag color="blue">{type}</Tag>
  return <Tag>{type}</Tag>
}

/**
 * Build a column comparison table showing source vs target values.
 * Highlights which columns have differences.
 */
function buildComparisonTable(sourceRecord, targetRecord, columnNames) {
  const rows = []
  const seen = new Set()

  // Add all columns from source
  if (sourceRecord) {
    for (const col of Object.keys(sourceRecord)) {
      if (!seen.has(col)) {
        seen.add(col)
        rows.push({
          key: col,
          column: col,
          source: sourceRecord[col],
          target: targetRecord?.[col] ?? null,
        })
      }
    }
  }

  // Add any columns only in target
  if (targetRecord) {
    for (const col of Object.keys(targetRecord)) {
      if (!seen.has(col)) {
        seen.add(col)
        rows.push({
          key: col,
          column: col,
          source: sourceRecord?.[col] ?? null,
          target: targetRecord[col],
        })
      }
    }
  }

  return rows
}

export function DetailedRowComparison({
  samples,
  comparedColumns = [],
  mismatchType = 'value_mismatch',
}) {
  if (!samples?.length) return null

  const isMissing = mismatchType === 'missing_in_target'
  const isExtra = mismatchType === 'extra_in_target'
  const isValue = mismatchType === 'value_mismatch'

  // For missing and extra, we show single rows
  if (isMissing || isExtra) {
    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {samples.map((sample, idx) => {
          const detail = sample.row_detail
          if (!detail?.source_record && !detail?.target_record) return null

          const rows = buildComparisonTable(
            detail.source_record,
            detail.target_record,
            comparedColumns
          )

          return (
            <Card key={`${sample.uid}-${idx}`} size="small" title={`UID: ${sample.uid}`}>
              <Space direction="vertical" size="small" style={{ width: '100%', marginBottom: 12 }}>
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  {isMissing
                    ? 'This row exists in source but not in target — all source values:'
                    : 'This row exists in target but not in source — all target values:'}
                </Typography.Paragraph>
              </Space>
              <Table
                size="small"
                pagination={false}
                scroll={{ x: 'max-content' }}
                columns={[
                  {
                    title: 'Column',
                    dataIndex: 'column',
                    key: 'column',
                    width: 150,
                    render: (col) => <Typography.Text code>{col}</Typography.Text>,
                  },
                  ...(isMissing
                    ? [
                        {
                          title: 'Source Value',
                          dataIndex: 'source',
                          key: 'source',
                          render: (val) => columnValueCell(val),
                        },
                      ]
                    : [
                        {
                          title: 'Target Value',
                          dataIndex: 'target',
                          key: 'target',
                          render: (val) => columnValueCell(val),
                        },
                      ]),
                ]}
                dataSource={rows}
              />
            </Card>
          )
        })}
      </Space>
    )
  }

  // For value mismatches, group by UID and show side-by-side comparison
  const groupedByUid = {}
  for (const sample of samples) {
    if (!groupedByUid[sample.uid]) {
      groupedByUid[sample.uid] = []
    }
    groupedByUid[sample.uid].push(sample)
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {Object.entries(groupedByUid).map(([uid, uidSamples]) => {
        const detail = uidSamples[0]?.row_detail
        if (!detail?.source_record || !detail?.target_record) return null

        const comparisonRows = buildComparisonTable(
          detail.source_record,
          detail.target_record,
          comparedColumns
        )

        // Highlight which columns are part of the mismatch
        const mismatchColumns = new Set(uidSamples.map((s) => s.column_name).filter(Boolean))

        return (
          <Card key={uid} size="small" title={`UID: ${uid}`}>
            <Space direction="vertical" size="small" style={{ width: '100%', marginBottom: 12 }}>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                Full row context (columns with value differences shown highlighted):
              </Typography.Paragraph>
            </Space>
            <Table
              size="small"
              pagination={false}
              scroll={{ x: 'max-content' }}
              columns={[
                {
                  title: 'Column',
                  dataIndex: 'column',
                  key: 'column',
                  width: 150,
                  render: (col) => {
                    const isMismatched = mismatchColumns.has(col)
                    return (
                      <div
                        style={{
                          background: isMismatched ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                          padding: isMismatched ? '2px 6px' : 0,
                          borderRadius: 4,
                        }}
                      >
                        <Typography.Text
                          code
                          strong={isMismatched}
                          style={{
                            color: isMismatched ? '#1e40af' : 'inherit',
                          }}
                        >
                          {col}
                        </Typography.Text>
                        {isMismatched ? (
                          <Tag color="blue" style={{ marginLeft: 8 }}>
                            Differs
                          </Tag>
                        ) : null}
                      </div>
                    )
                  },
                },
                {
                  title: (
                    <span>
                      Expected <Typography.Text type="secondary">(source)</Typography.Text>
                    </span>
                  ),
                  key: 'source',
                  width: 200,
                  render: (_, row) => {
                    const isMismatched = mismatchColumns.has(row.column)
                    return (
                      <div
                        style={{
                          background: isMismatched ? 'rgba(34, 197, 94, 0.15)' : 'transparent',
                          padding: isMismatched ? '4px 8px' : '2px 0',
                          borderRadius: 4,
                          color: isMismatched ? '#166534' : 'inherit',
                          fontWeight: isMismatched ? 500 : 'normal',
                        }}
                      >
                        {columnValueCell(row.source)}
                      </div>
                    )
                  },
                },
                {
                  title: (
                    <span>
                      Actual <Typography.Text type="secondary">(target)</Typography.Text>
                    </span>
                  ),
                  key: 'target',
                  width: 200,
                  render: (_, row) => {
                    const isMismatched = mismatchColumns.has(row.column)
                    return (
                      <div
                        style={{
                          background: isMismatched ? 'rgba(239, 68, 68, 0.14)' : 'transparent',
                          padding: isMismatched ? '4px 8px' : '2px 0',
                          borderRadius: 4,
                          color: isMismatched ? '#991b1b' : 'inherit',
                          fontWeight: isMismatched ? 500 : 'normal',
                        }}
                      >
                        {columnValueCell(row.target)}
                      </div>
                    )
                  },
                },
              ]}
              dataSource={comparisonRows}
            />
          </Card>
        )
      })}
    </Space>
  )
}
