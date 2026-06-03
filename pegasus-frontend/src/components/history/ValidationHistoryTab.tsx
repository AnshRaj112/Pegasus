import React from 'react'
import { Table, Button, Space, Popconfirm, message, Tag } from 'antd'
import { Eye, Trash2 } from 'lucide-react'
import type { ValidationRun } from '../../types'

interface ValidationHistoryTabProps {
  runs?: ValidationRun[]
  loading?: boolean
  onViewReport?: (runId: string) => void
  onDelete?: (runId: string) => void
}

export const ValidationHistoryTab: React.FC<ValidationHistoryTabProps> = ({
  runs = [],
  loading = false,
  onViewReport,
  onDelete,
}) => {
  const columns = [
    {
      title: 'Source',
      dataIndex: 'source_filename',
      key: 'source',
      render: (filename: string, record: ValidationRun) => (
        <div>
          <div style={{ fontWeight: 600 }}>{filename}</div>
          <div style={{ fontSize: '12px', color: '#999' }}>{record.source_path}</div>
        </div>
      ),
    },
    {
      title: 'Target',
      dataIndex: 'target_filename',
      key: 'target',
      render: (filename: string, record: ValidationRun) => (
        <div>
          <div style={{ fontWeight: 600 }}>{filename}</div>
          <div style={{ fontSize: '12px', color: '#999' }}>{record.target_path}</div>
        </div>
      ),
    },
    {
      title: 'Mapping Counts',
      dataIndex: 'mismatch_counts',
      key: 'mapping',
      render: (counts: any) => `${counts?.missing_in_target || 0} missing, ${counts?.extra_in_target || 0} extra`,
    },
    {
      title: 'Duration',
      dataIndex: 'durations',
      key: 'duration',
      render: (durations: any) => {
        const total = durations?.total_seconds || 0
        const mins = Math.floor(total / 60)
        const secs = total % 60
        return `${mins}m ${secs}s`
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          success: 'green',
          failed: 'red',
          pending: 'orange',
        }
        return <span style={{ color: colorMap[status] || '#999' }}>{status}</span>
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: ValidationRun) => (
        <Space>
          <Button
            size="small"
            type="link"
            icon={<Eye size={14} />}
            onClick={() => onViewReport?.(record.run_id)}
          >
            View Report
          </Button>
          <Popconfirm
            title="Delete"
            description="Are you sure you want to delete this record?"
            onConfirm={() => {
              onDelete?.(record.run_id)
              message.success('Deleted')
            }}
          >
            <Button size="small" danger icon={<Trash2 size={14} />}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Table columns={columns} dataSource={runs} rowKey="run_id" loading={loading} pagination={{ pageSize: 10 }} />
  )
}
