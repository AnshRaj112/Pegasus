import React, { useMemo, useState } from 'react'
import { Card, Table, Tag, Descriptions, Space, Typography, Pagination, Badge } from 'antd'

const { Title, Text } = Typography

interface ReportSectionProps {
  type: string
  samples: any[]
}

function formatValue(value: any) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function mismatchDisplayValues(row: any) {
  const detail = row.row_detail ?? {}
  const sourceRecord = detail.source_record
  const targetRecord = detail.target_record
  const columnName = row.column_name

  if (
    columnName &&
    sourceRecord &&
    typeof sourceRecord === 'object' &&
    columnName in sourceRecord
  ) {
    return {
      source: sourceRecord[columnName],
      target:
        targetRecord && typeof targetRecord === 'object' && columnName in targetRecord
          ? targetRecord[columnName]
          : row.target_value,
    }
  }

  return { source: row.source_value, target: row.target_value }
}

export default function ReportSection({ type, samples = [] }: ReportSectionProps) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  const visibleSamples = useMemo(() => {
    const start = (page - 1) * pageSize
    return samples.slice(start, start + pageSize)
  }, [samples, page, pageSize])

  const typeLabel =
    type === 'missing_in_target'
      ? 'Missing in target'
      : type === 'extra_in_target'
        ? 'Extra in target'
        : 'Mismatched'

  const typeColor =
    type === 'missing_in_target'
      ? 'volcano'
      : type === 'extra_in_target'
        ? 'blue'
        : 'gold'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              {typeLabel} Rows
            </Title>
            <Text type="secondary">
              {type === 'missing_in_target'
                ? 'Records that exist in the source file but were not found in the target file.'
                : type === 'extra_in_target'
                  ? 'Records that exist in the target file but were not found in the source file.'
                  : 'Records where the same row exists in both files but one or more values differ.'}
            </Text>
          </div>
          <Badge count={`${samples.length} total rows`} overflowCount={99999} style={{ backgroundColor: '#52c41a' }} />
        </div>
      </Card>

      {visibleSamples.map((row, idx) => {
        const detail = row.row_detail ?? {}
        const sourceRecord = detail.source_record ?? {}
        const targetRecord = detail.target_record ?? {}
        const { source: displaySource, target: displayTarget } = mismatchDisplayValues(row)

        return (
          <Card
            key={`${row.uid}-${idx}`}
            title={
              <Space>
                <Text strong style={{ fontSize: '15px' }}>UID: {formatValue(row.uid)}</Text>
                <Tag color={typeColor}>{typeLabel.toUpperCase()}</Tag>
              </Space>
            }
            bordered={false}
            style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}
          >
            {/* Metadata (Column, Source Value, Target Value) */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px', padding: '12px', background: '#f9fafb', borderRadius: '8px' }}>
              <div>
                <Text type="secondary" style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 600 }}>Column Name</Text>
                <div style={{ fontWeight: 600, color: '#1f2937' }}>{formatValue(row.column_name || '—')}</div>
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 600 }}>Expected Value (Source)</Text>
                <div style={{ fontWeight: 600, color: '#16a34a' }}>{formatValue(displaySource)}</div>
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 600 }}>Actual Value (Target)</Text>
                <div style={{ fontWeight: 600, color: '#dc2626' }}>{formatValue(displayTarget)}</div>
              </div>
            </div>

            {/* Side-by-side Source and Target Records */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
              {/* Source Record */}
              <Card
                title="Source Record Data"
                size="small"
                styles={{ header: { background: '#f0fdf4', color: '#166534' } }}
                style={{ border: '1px solid #bbf7d0' }}
              >
                {Object.keys(sourceRecord).length > 0 ? (
                  <Descriptions column={1} size="small" bordered>
                    {Object.entries(sourceRecord).map(([k, v]) => (
                      <Descriptions.Item key={k} label={k}>
                        {formatValue(v)}
                      </Descriptions.Item>
                    ))}
                  </Descriptions>
                ) : (
                  <Text type="secondary">Source record details are not available.</Text>
                )}
              </Card>

              {/* Target Record */}
              <Card
                title="Target Record Data"
                size="small"
                styles={{ header: { background: '#fef2f2', color: '#991b1b' } }}
                style={{ border: '1px solid #fecaca' }}
              >
                {Object.keys(targetRecord).length > 0 ? (
                  <Descriptions column={1} size="small" bordered>
                    {Object.entries(targetRecord).map(([k, v]) => (
                      <Descriptions.Item key={k} label={k}>
                        {formatValue(v)}
                      </Descriptions.Item>
                    ))}
                  </Descriptions>
                ) : (
                  <Text type="secondary">Target record details are not available.</Text>
                )}
              </Card>
            </div>
          </Card>
        )
      })}

      {samples.length > 0 ? (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '12px' }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={samples.length}
            onChange={(p, sz) => {
              setPage(p)
              if (sz) setPageSize(sz)
            }}
            showSizeChanger
            pageSizeOptions={['10', '25', '50', '100']}
          />
        </div>
      ) : (
        <Card bordered={false} style={{ textAlign: 'center', padding: '40px 0', color: '#9ca3af' }}>
          No records match the current filter.
        </Card>
      )}
    </div>
  )
}
