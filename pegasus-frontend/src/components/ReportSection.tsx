import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Card, Col, Descriptions, Empty, InputNumber, Pagination as AntPagination, Row, Select, Space, Statistic, Tag, Typography } from 'antd'

const PAGE_SIZE = 10
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

const variantStyles = {
  mismatched: {
    badge: { background: '#FEF3C7', color: '#92400E', border: '1px solid #FCD34D' },
    accent: { borderColor: '#FCD34D', background: 'rgba(254, 243, 199, 0.25)' },
    title: 'Mismatched values',
    empty: 'No mismatched rows match the current filter.',
  },
  missing_in_target: {
    badge: { background: '#FFE4E6', color: '#9F1239', border: '1px solid #FDA4AF' },
    accent: { borderColor: '#FDA4AF', background: 'rgba(255, 228, 230, 0.3)' },
    title: 'Missing in target',
    empty: 'No missing rows match the current filter.',
  },
  extra_in_target: {
    badge: { background: '#E0F2FE', color: '#075985', border: '1px solid #7DD3FC' },
    accent: { borderColor: '#7DD3FC', background: 'rgba(224, 242, 254, 0.35)' },
    title: 'Extra in target',
    empty: 'No extra rows match the current filter.',
  },
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function DetailBlock({ title, record, tone }) {
  if (!record || typeof record !== 'object') return null

  const palette =
    tone === 'source'
      ? { border: '#BBF7D0', background: '#F0FDF4', title: '#14532D' }
      : { border: '#FECACA', background: '#FEF2F2', title: '#7F1D1D' }

  const entries = Object.entries(record)

  return (
    <Card size="small" style={{ borderRadius: 16, borderColor: palette.border, background: palette.background }} styles={{ body: { padding: 16 } }}>
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Typography.Text strong style={{ color: palette.title }}>{title}</Typography.Text>
          <Tag>{entries.length} fields</Tag>
        </Space>
        <Descriptions column={{ xs: 1, sm: 2 }} size="small" bordered={false} items={entries.map(([key, value]) => ({
          key,
          label: <Typography.Text type="secondary" style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{key}</Typography.Text>,
          children: <Typography.Text style={{ wordBreak: 'break-word', fontFamily: 'monospace', color: '#111827' }}>{formatValue(value)}</Typography.Text>,
        }))} />
      </Space>
    </Card>
  )
}

function mismatchDisplayValues(row) {
  const detail = row.row_detail ?? {}
  const sourceRecord = detail.source_record
  const targetRecord = detail.target_record
  const columnName = row.column_name

  if (columnName && sourceRecord && typeof sourceRecord === 'object' && columnName in sourceRecord) {
    return {
      source: sourceRecord[columnName],
      target: targetRecord && typeof targetRecord === 'object' && columnName in targetRecord ? targetRecord[columnName] : row.target_value,
    }
  }

  return { source: row.source_value, target: row.target_value }
}

function RowCard({ row, variant }) {
  const style = variantStyles[variant] ?? variantStyles.mismatched
  const typeLabel =
    variant === 'missing_in_target'
      ? 'Missing in target'
      : variant === 'extra_in_target'
        ? 'Extra in target'
        : 'Mismatched'

  const detail = row.row_detail ?? {}
  const hasSource = detail.source_record && typeof detail.source_record === 'object'
  const hasTarget = detail.target_record && typeof detail.target_record === 'object'
  const { source: displaySource, target: displayTarget } = mismatchDisplayValues(row)

  return (
    <Card style={{ borderRadius: 24, border: `1px solid ${style.accent.borderColor}`, background: style.accent.background, boxShadow: '0 8px 18px rgba(15, 23, 42, 0.04)' }} styles={{ body: { padding: 20 } }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'space-between', alignItems: 'flex-start' }} wrap>
          <Space direction="vertical" size={4}>
            <Typography.Text style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.28em', textTransform: 'uppercase', color: '#64748B' }}>Record</Typography.Text>
            <Typography.Title level={4} style={{ margin: 0, color: '#0F172A' }}>UID {formatValue(row.uid)}</Typography.Title>
            <Typography.Paragraph style={{ marginBottom: 0, color: '#475569' }}>
              {variant === 'missing_in_target'
                ? 'Present in the source file but absent from the target file.'
                : variant === 'extra_in_target'
                  ? 'Present in the target file but absent from the source file.'
                  : 'Values differ between source and target for at least one shared column.'}
            </Typography.Paragraph>
          </Space>
          <Tag style={{ marginInlineEnd: 0, padding: '4px 10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', ...style.badge }}>
            {typeLabel}
          </Tag>
        </Space>

        <Row gutter={[12, 12]}>
          <Col xs={24} md={8}>
            <Card size="small" style={{ borderRadius: 16, background: 'rgba(255,255,255,0.82)' }} styles={{ body: { padding: 16 } }}>
              <Typography.Text style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748B' }}>Column</Typography.Text>
              <Typography.Paragraph style={{ marginBottom: 0, marginTop: 8, wordBreak: 'break-word', fontWeight: 600, color: '#0F172A' }}>{formatValue(row.column_name)}</Typography.Paragraph>
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card size="small" style={{ borderRadius: 16, background: 'rgba(255,255,255,0.82)' }} styles={{ body: { padding: 16 } }}>
              <Typography.Text style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748B' }}>Expected (source)</Typography.Text>
              <Typography.Paragraph style={{ marginBottom: 0, marginTop: 8, wordBreak: 'break-word', fontWeight: 600, color: '#166534' }}>{formatValue(displaySource)}</Typography.Paragraph>
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card size="small" style={{ borderRadius: 16, background: 'rgba(255,255,255,0.82)' }} styles={{ body: { padding: 16 } }}>
              <Typography.Text style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748B' }}>Actual (target)</Typography.Text>
              <Typography.Paragraph style={{ marginBottom: 0, marginTop: 8, wordBreak: 'break-word', fontWeight: 600, color: '#991B1B' }}>{formatValue(displayTarget)}</Typography.Paragraph>
            </Card>
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} lg={12}>
            {hasSource ? (
              <DetailBlock title="Source record" record={detail.source_record} tone="source" />
            ) : (
              <Card size="small" style={{ borderRadius: 16, borderStyle: 'dashed', background: 'rgba(255,255,255,0.6)' }} styles={{ body: { padding: 16 } }}>
                <Typography.Text type="secondary">Source record details are not available.</Typography.Text>
              </Card>
            )}
          </Col>
          <Col xs={24} lg={12}>
            {hasTarget ? (
              <DetailBlock title="Target record" record={detail.target_record} tone="target" />
            ) : (
              <Card size="small" style={{ borderRadius: 16, borderStyle: 'dashed', background: 'rgba(255,255,255,0.6)' }} styles={{ body: { padding: 16 } }}>
                <Typography.Text type="secondary">Target record details are not available.</Typography.Text>
              </Card>
            )}
          </Col>
        </Row>
      </Space>
    </Card>
  )
}

function Pagination({ page, totalPages, totalItems, pageSize, onPageChange, onPageSizeChange }) {
  if (!totalItems) return null

  const start = Math.min((page - 1) * pageSize + 1, totalItems)
  const end = Math.min(page * pageSize, totalItems)

  return (
    <Card size="small" style={{ borderRadius: 20, borderColor: '#E2E8F0' }} styles={{ body: { padding: 16 } }}>
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Typography.Text style={{ color: '#475569' }}>
          Showing <Typography.Text strong>{start}</Typography.Text> to <Typography.Text strong>{end}</Typography.Text> of <Typography.Text strong>{totalItems}</Typography.Text> rows
        </Typography.Text>
        <Space wrap style={{ width: '100%', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space wrap size={8}>
            <Button onClick={() => onPageChange(page - 1)} disabled={page <= 1}>Previous</Button>
            <Tag style={{ marginInlineEnd: 0 }}>Page {page} of {totalPages}</Tag>
            <Button onClick={() => onPageChange(page + 1)} disabled={page >= totalPages}>Next</Button>
          </Space>
          <Space wrap size={12}>
            <Space size={6} align="center">
              <Typography.Text style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748B' }}>Go to</Typography.Text>
              <InputNumber
                min={1}
                max={totalPages}
                value={page}
                onChange={(nextPage) => {
                  const numericPage = Number(nextPage)
                  if (Number.isFinite(numericPage)) onPageChange(Math.min(Math.max(1, Math.floor(numericPage)), totalPages))
                }}
                style={{ width: 88 }}
              />
            </Space>
            <Space size={6} align="center">
              <Typography.Text style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748B' }}>Rows</Typography.Text>
              <Select
                value={pageSize}
                onChange={(nextSize) => onPageSizeChange(Number(nextSize))}
                style={{ width: 104 }}
                options={PAGE_SIZE_OPTIONS.map((option) => ({ value: option, label: String(option) }))}
              />
            </Space>
          </Space>
        </Space>
      </Space>
    </Card>
  )
}

export function ReportSection({ type, samples = [] }) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const firstRowRef = useRef(null)
  const style = variantStyles[type] ?? variantStyles.mismatched
  const totalPages = Math.max(1, Math.ceil(samples.length / pageSize))
  const safePage = Math.min(page, totalPages)

  const visibleSamples = useMemo(() => {
    const start = (safePage - 1) * pageSize
    return samples.slice(start, start + pageSize)
  }, [samples, safePage, pageSize])

  useEffect(() => {
    if (!visibleSamples.length) return
    firstRowRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [safePage, visibleSamples.length])

  return (
    <Card style={{ borderRadius: 24, borderColor: '#E2E8F0' }} styles={{ body: { padding: 24 } }}>
      <Space direction="vertical" size={20} style={{ width: '100%' }}>
        <Space wrap style={{ width: '100%', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <Space direction="vertical" size={4}>
            <Typography.Text style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.28em', textTransform: 'uppercase', color: '#64748B' }}>Section</Typography.Text>
            <Typography.Title level={2} style={{ margin: 0, color: '#0F172A' }}>{style.title}</Typography.Title>
            <Typography.Paragraph style={{ marginBottom: 0, maxWidth: 960, color: '#475569' }}>
              {type === 'missing_in_target'
                ? 'Records that exist in the source file but were not found in the target file.'
                : type === 'extra_in_target'
                  ? 'Records that exist in the target file but were not found in the source file.'
                  : 'Records where the same row exists in both files but one or more values differ.'}
            </Typography.Paragraph>
          </Space>

          <Card size="small" style={{ borderRadius: 16, background: '#F8FAFC', borderColor: '#E2E8F0' }} styles={{ body: { padding: 16 } }}>
            <Statistic value={samples.length} suffix="total rows" />
            <Typography.Text type="secondary">Showing up to {pageSize} rows per page</Typography.Text>
          </Card>
        </Space>

        {samples.length ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Row gutter={[12, 12]}>
              <Col xs={24} md={8}>
                <Card size="small" style={{ borderRadius: 16, background: '#F8FAFC' }} styles={{ body: { padding: 16 } }}>
                  <Typography.Text style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748B' }}>Active page</Typography.Text>
                  <Typography.Title level={3} style={{ margin: '8px 0 0', color: '#0F172A' }}>{safePage}</Typography.Title>
                </Card>
              </Col>
              <Col xs={24} md={8}>
                <Card size="small" style={{ borderRadius: 16, background: '#F8FAFC' }} styles={{ body: { padding: 16 } }}>
                  <Typography.Text style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748B' }}>Page size</Typography.Text>
                  <Typography.Title level={3} style={{ margin: '8px 0 0', color: '#0F172A' }}>{pageSize}</Typography.Title>
                </Card>
              </Col>
              <Col xs={24} md={8}>
                <Card size="small" style={{ borderRadius: 16, background: '#F8FAFC' }} styles={{ body: { padding: 16 } }}>
                  <Typography.Text style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748B' }}>Total pages</Typography.Text>
                  <Typography.Title level={3} style={{ margin: '8px 0 0', color: '#0F172A' }}>{totalPages}</Typography.Title>
                </Card>
              </Col>
            </Row>

            {visibleSamples.map((row, index) => (
              <div key={`${row.uid}-${row.mismatch_type}-${row.column_name ?? 'column'}`} ref={index === 0 ? firstRowRef : null}>
                <RowCard row={row} variant={type} />
              </div>
            ))}

            <Pagination
              page={safePage}
              totalPages={totalPages}
              totalItems={samples.length}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={(nextPageSize) => {
                setPageSize(nextPageSize)
                setPage(1)
              }}
            />
          </Space>
        ) : (
          <Empty
            style={{ padding: '40px 0' }}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={<Typography.Text type="secondary">{style.empty}</Typography.Text>}
          />
        )}
      </Space>
    </Card>
  )
}

export default ReportSection