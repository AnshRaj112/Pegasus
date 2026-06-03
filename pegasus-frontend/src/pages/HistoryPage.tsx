import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Table, Tabs, Tag, Button, Space, Popconfirm, Tooltip, Badge, Typography, message, Modal, Row, Col, Descriptions } from 'antd'
import { EyeOutlined, DeleteOutlined, PlayCircleOutlined, ExclamationCircleOutlined, SyncOutlined } from '@ant-design/icons'
import {
  basename,
  fetchValidationHistory,
  fetchValidationHistoryDetail,
  fetchValidationHistoryMismatches,
  formatDuration,
  deleteValidationHistoryRun,
  deleteValidationHistoryByPair,
  deleteValidationHistoryAll,
  fetchLocalColumnPreview,
} from '../api/validationHistory'

const { Title, Paragraph, Text } = Typography

// Helper: IST Converter
function formatToIST(iso: string | undefined) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const istMs = d.getTime() + 330 * 60 * 1000 // +5:30
  const ist = new Date(istMs)
  const YYYY = ist.getUTCFullYear()
  const MM = ist.getUTCMonth()
  const DD = String(ist.getUTCDate()).padStart(2, '0')
  const hour24 = ist.getUTCHours()
  const hour12 = hour24 % 12 === 0 ? 12 : hour24 % 12
  const mm = String(ist.getUTCMinutes()).padStart(2, '0')
  const suffix = hour24 >= 12 ? 'PM' : 'AM'
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return `${months[MM]} ${DD}, ${YYYY} ${hour12}:${mm} ${suffix} IST`
}

function parseHistoryRowDetail(rowDetail: any) {
  if (!rowDetail) return null
  if (typeof rowDetail === 'object') return rowDetail
  if (typeof rowDetail !== 'string') return null
  const trimmed = rowDetail.trim()
  if (!trimmed || trimmed === '{}') return null
  try {
    return JSON.parse(trimmed)
  } catch {
    return null
  }
}

function normalizeHistoryMismatchRow(row: any) {
  return {
    ...row,
    row_detail: parseHistoryRowDetail(row.row_detail),
  }
}

function buildHistoryReportResult(detail: any, mismatches: any) {
  const items = (mismatches?.items ?? []).map(normalizeHistoryMismatchRow)
  const mismatchCounts = detail?.mismatch_counts ?? {
    missing_in_target: 0,
    extra_in_target: 0,
    value_mismatch: 0,
  }
  const totalMismatchRecords =
    Number(mismatchCounts.missing_in_target ?? 0) +
    Number(mismatchCounts.extra_in_target ?? 0) +
    Number(mismatchCounts.value_mismatch ?? 0)

  const groupedItems: any = {
    missing_in_target: [],
    extra_in_target: [],
    value_mismatch: [],
  }

  for (const item of items) {
    if (groupedItems[item.mismatch_type]) {
      groupedItems[item.mismatch_type].push(item)
    }
  }

  return {
    ...detail,
    run_id: detail?.run_id,
    summary: {
      is_match: detail?.is_match,
      source_row_count: detail?.source_row_count,
      target_row_count: detail?.target_row_count,
      total_mismatch_records: totalMismatchRecords,
    },
    mismatch_counts: mismatchCounts,
    mismatch_samples: items,
    mismatch_sample_groups: groupedItems,
  }
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('runs')

  // Validation history state
  const [valHistory, setValHistory] = useState<any[]>([])
  const [valTotal, setValTotal] = useState(0)
  const [valPage, setValPage] = useState(1)
  const [valPageSize, setValPageSize] = useState(15)
  const [valLoading, setValLoading] = useState(false)

  // Mapping history state
  const [mapHistory, setMapHistory] = useState<any[]>([])
  const [mapTotal, setMapTotal] = useState(0)
  const [mapPage, setMapPage] = useState(1)
  const [mapPageSize, setMapPageSize] = useState(15)
  const [mapLoading, setMapLoading] = useState(false)

  // Selected run detail modal state
  const [selectedRun, setSelectedRun] = useState<any>(null)
  const [selectedRunLoading, setSelectedRunLoading] = useState(false)
  const [detailedReportLoading, setDetailedReportLoading] = useState(false)

  const loadValidationHistory = useCallback(async () => {
    setValLoading(true)
    try {
      const offset = (valPage - 1) * valPageSize
      const data = await fetchValidationHistory({ limit: valPageSize, offset })
      setValHistory(Array.isArray(data.items) ? data.items : [])
      setValTotal(data.total ?? 0)
    } catch (e: any) {
      message.error(e.message || 'Failed to fetch validation runs history')
    } finally {
      setValLoading(false)
    }
  }, [valPage, valPageSize])

  const loadMappingHistory = useCallback(async () => {
    setMapLoading(true)
    try {
      // In this setup, we get mappings by calling fetchValidationHistory with get_saved_mappings: true
      const offset = (mapPage - 1) * mapPageSize
      const data = await fetchValidationHistory({ limit: mapPageSize, offset, onlyWithMapping: true })
      setMapHistory(Array.isArray(data.items) ? data.items : [])
      setMapTotal(data.total ?? 0)
    } catch (e: any) {
      message.error(e.message || 'Failed to fetch mapping history')
    } finally {
      setMapLoading(false)
    }
  }, [mapPage, mapPageSize])

  useEffect(() => {
    if (activeTab === 'runs') {
      loadValidationHistory()
    } else {
      loadMappingHistory()
    }
  }, [activeTab, loadValidationHistory, loadMappingHistory])

  // Delete handlers
  const handleDeleteRun = async (runId: string) => {
    try {
      await deleteValidationHistoryRun(runId)
      message.success('Validation run history deleted successfully')
      loadValidationHistory()
    } catch (e: any) {
      message.error(e.message || 'Delete run failed')
    }
  }

  const handleDeleteMappingPair = async (sourcePath: string, targetPath: string) => {
    try {
      await deleteValidationHistoryByPair(sourcePath, targetPath)
      message.success('File pair mapping definition deleted successfully')
      loadMappingHistory()
    } catch (e: any) {
      message.error(e.message || 'Delete mapping failed')
    }
  }

  const handleClearAllHistory = async () => {
    try {
      await deleteValidationHistoryAll()
      message.success('All history and mapping configs cleared')
      loadValidationHistory()
      loadMappingHistory()
    } catch (e: any) {
      message.error(e.message || 'Failed to clear all data')
    }
  }

  const handleOpenDetailedReport = async (run: any) => {
    setDetailedReportLoading(true)
    try {
      const detail = await fetchValidationHistoryDetail(run.run_id)
      // Fetch mismatch samples up to 1000 items
      const mismatches = await fetchValidationHistoryMismatches(run.run_id, { limit: 1000 })
      const finalResult = buildHistoryReportResult(detail, mismatches)
      navigate('/report', {
        state: {
          result: finalResult,
          reportTitle: `${basename(run.source_path)} vs ${basename(run.target_path)} (${formatToIST(run.completed_at || run.created_at)})`
        }
      })
    } catch (e: any) {
      message.error(e.message || 'Failed to construct detailed report.')
    } finally {
      setDetailedReportLoading(false)
    }
  }

  const handleResumeMapping = async (row: any) => {
    // Navigate back to Configure Mapping with state to preload this configuration
    navigate('/configure-mapping', {
      state: {
        preloadSourcePath: row.source_path,
        preloadTargetPath: row.target_path,
        preloadUidColumn: row.uid_column || 'id',
        preloadDelimiter: row.delimiter || 'auto',
      }
    })
  }

  const handleShowRunDetail = async (runId: string) => {
    setSelectedRunLoading(true)
    try {
      const detail = await fetchValidationHistoryDetail(runId)
      setSelectedRun(detail)
    } catch (e: any) {
      message.error(e.message || 'Failed to load details')
    } finally {
      setSelectedRunLoading(false)
    }
  }

  const runsColumns = [
    {
      title: 'Run Files',
      key: 'files',
      render: (_: any, row: any) => (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <Text strong style={{ fontSize: '13px' }}>
            {basename(row.source_path)} <span style={{ color: '#bfbfbf', fontWeight: 'normal' }}>vs</span> {basename(row.target_path)}
          </Text>
          <code style={{ fontSize: '10px', color: '#8c8c8c', marginTop: '2px', wordBreak: 'break-all' }}>
            Source: {row.source_path}
          </code>
          <code style={{ fontSize: '10px', color: '#8c8c8c', wordBreak: 'break-all' }}>
            Target: {row.target_path}
          </code>
        </div>
      )
    },
    {
      title: 'Status',
      dataIndex: 'is_match',
      key: 'is_match',
      width: 130,
      render: (isMatch: boolean, row: any) => {
        if (row.status && row.status !== 'completed') {
          return <Tag color="blue">{row.status.toUpperCase()}</Tag>
        }
        return (
          <Tag color={isMatch ? 'green' : 'red'}>
            {isMatch ? 'FULL MATCH' : 'MISMATCHES'}
          </Tag>
        )
      }
    },
    {
      title: 'Duration',
      dataIndex: 'completed_at',
      key: 'duration',
      width: 120,
      render: (_: any, row: any) => {
        const start = new Date(row.created_at).getTime()
        const end = row.completed_at ? new Date(row.completed_at).getTime() : 0
        if (!end || end < start) return '—'
        return formatDuration(end - start)
      }
    },
    {
      title: 'Valid Completed At',
      dataIndex: 'completed_at',
      key: 'completed_at',
      width: 220,
      render: (val: string) => formatToIST(val) || '—'
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      align: 'right' as const,
      render: (_: any, row: any) => (
        <Space size="middle">
          {row.status === 'completed' && (
            <Tooltip title="View Detailed Report">
              <Button
                type="link"
                icon={<EyeOutlined />}
                onClick={() => handleOpenDetailedReport(row)}
                loading={detailedReportLoading}
              />
            </Tooltip>
          )}
          <Tooltip title="View Run Details">
            <Button
              type="text"
              onClick={() => handleShowRunDetail(row.run_id)}
            >
              Info
            </Button>
          </Tooltip>
          <Popconfirm
            title="Delete Validation History"
            description="Are you sure you want to delete this specific run record? This action is permanent."
            onConfirm={() => handleDeleteRun(row.run_id)}
            okText="Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    }
  ]

  const mappingsColumns = [
    {
      title: 'Mapped Files',
      key: 'files',
      render: (_: any, row: any) => (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <Text strong style={{ fontSize: '13px' }}>
            {basename(row.source_path)} <span style={{ color: '#bfbfbf', fontWeight: 'normal' }}>vs</span> {basename(row.target_path)}
          </Text>
          <code style={{ fontSize: '10px', color: '#8c8c8c', marginTop: '2px', wordBreak: 'break-all' }}>
            Source: {row.source_path}
          </code>
          <code style={{ fontSize: '10px', color: '#8c8c8c', wordBreak: 'break-all' }}>
            Target: {row.target_path}
          </code>
        </div>
      )
    },
    {
      title: 'Delimiter',
      dataIndex: 'delimiter',
      key: 'delimiter',
      width: 120,
      render: (val: string) => <Tag color="geekblue">{val || 'auto'}</Tag>
    },
    {
      title: 'Join UID Column',
      dataIndex: 'uid_column',
      key: 'uid_column',
      width: 140,
      render: (val: string) => <code>{val || 'id'}</code>
    },
    {
      title: 'Columns Mapped',
      dataIndex: 'column_mappings',
      key: 'column_mappings',
      width: 150,
      render: (val: any[]) => <Badge count={Array.isArray(val) ? val.length : 0} style={{ backgroundColor: '#52c41a' }} />
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      align: 'right' as const,
      render: (_: any, row: any) => (
        <Space size="middle">
          <Tooltip title="Preload & Edit Mapping Wizard">
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => handleResumeMapping(row)}
            >
              Resume
            </Button>
          </Tooltip>
          <Popconfirm
            title="Delete Mapping Setup"
            description="Are you sure you want to clear saved mappings and configurations for this pair?"
            onConfirm={() => handleDeleteMappingPair(row.source_path, row.target_path)}
            okText="Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    }
  ]

  const items = [
    {
      key: 'runs',
      label: 'Validation History Runs',
      children: (
        <Table
          columns={runsColumns}
          dataSource={valHistory}
          rowKey="run_id"
          loading={valLoading}
          pagination={{
            current: valPage,
            pageSize: valPageSize,
            total: valTotal,
            onChange: (p, sz) => {
              setValPage(p)
              if (sz) setValPageSize(sz)
            },
            showSizeChanger: true,
            pageSizeOptions: ['15', '25', '50', '100']
          }}
        />
      )
    },
    {
      key: 'mappings',
      label: 'Saved Mappings Definitions',
      children: (
        <Table
          columns={mappingsColumns}
          dataSource={mapHistory}
          rowKey={(record) => `${record.source_path}-${record.target_path}`}
          loading={mapLoading}
          pagination={{
            current: mapPage,
            pageSize: mapPageSize,
            total: mapTotal,
            onChange: (p, sz) => {
              setMapPage(p)
              if (sz) setMapPageSize(sz)
            },
            showSizeChanger: true,
            pageSizeOptions: ['15', '25', '50', '100']
          }}
        />
      )
    }
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>Pegasus History Logs</Title>
          <Paragraph type="secondary">
            View completed and running validation reports, or preload/manage your configured CSV mapping schema setups.
          </Paragraph>
        </div>
        <Popconfirm
          title="Clear Entire History"
          description="Are you absolutely sure you want to delete ALL historical validations and mapping settings? This cannot be undone."
          onConfirm={handleClearAllHistory}
          okText="Clear All"
          cancelText="Cancel"
          okButtonProps={{ danger: true }}
        >
          <Button danger type="dashed">
            Clear All History Logs
          </Button>
        </Popconfirm>
      </div>

      <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key)}
          items={items}
          size="large"
        />
      </Card>

      {/* Selected Run Info Modal */}
      <Modal
        title="Validation Run Details"
        open={!!selectedRun}
        onCancel={() => setSelectedRun(null)}
        footer={[
          <Button key="close" onClick={() => setSelectedRun(null)}>
            Close
          </Button>
        ]}
        width={680}
      >
        {selectedRun && (
          <Descriptions bordered column={2} size="small" style={{ marginTop: '14px' }}>
            <Descriptions.Item label="Run ID" span={2}>
              <code>{selectedRun.run_id}</code>
            </Descriptions.Item>
            <Descriptions.Item label="Source File" span={2}>
              <Text strong>{basename(selectedRun.source_path)}</Text>
              <div style={{ fontSize: '11px', color: '#8c8c8c' }}>{selectedRun.source_path}</div>
            </Descriptions.Item>
            <Descriptions.Item label="Target File" span={2}>
              <Text strong>{basename(selectedRun.target_path)}</Text>
              <div style={{ fontSize: '11px', color: '#8c8c8c' }}>{selectedRun.target_path}</div>
            </Descriptions.Item>
            <Descriptions.Item label="Is Match">
              <Tag color={selectedRun.is_match ? 'green' : 'red'}>
                {selectedRun.is_match ? 'MATCH' : 'MISMATCH'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color="cyan">{String(selectedRun.status).toUpperCase()}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Source Row Count">
              {selectedRun.source_row_count ?? '—'}
            </Descriptions.Item>
            <Descriptions.Item label="Target Row Count">
              {selectedRun.target_row_count ?? '—'}
            </Descriptions.Item>
            <Descriptions.Item label="Missing in Target">
              {selectedRun.mismatch_counts?.missing_in_target ?? 0}
            </Descriptions.Item>
            <Descriptions.Item label="Extra in Target">
              {selectedRun.mismatch_counts?.extra_in_target ?? 0}
            </Descriptions.Item>
            <Descriptions.Item label="Value Mismatch">
              {selectedRun.mismatch_counts?.value_mismatch ?? 0}
            </Descriptions.Item>
            <Descriptions.Item label="Created At" span={2}>
              {formatToIST(selectedRun.created_at)}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}
