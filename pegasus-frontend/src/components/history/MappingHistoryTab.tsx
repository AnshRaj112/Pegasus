import React from 'react'
import { Table, Button, Popconfirm, message, Tag } from 'antd'
import { Trash2 } from 'lucide-react'

interface MappingHistoryTabProps {
  mappings?: any[]
  loading?: boolean
  onDelete?: (id: string) => void
}

export const MappingHistoryTab: React.FC<MappingHistoryTabProps> = ({
  mappings = [],
  loading = false,
  onDelete,
}) => {
  const columns = [
    {
      title: 'Source Details',
      dataIndex: 'source',
      key: 'source',
      render: (source: any) => (
        <div>
          <div style={{ fontWeight: 600 }}>{source?.name}</div>
          <div style={{ fontSize: '12px', color: '#999' }}>{source?.path}</div>
        </div>
      ),
    },
    {
      title: 'Target Details',
      dataIndex: 'target',
      key: 'target',
      render: (target: any) => (
        <div>
          <div style={{ fontWeight: 600 }}>{target?.name}</div>
          <div style={{ fontSize: '12px', color: '#999' }}>{target?.path}</div>
        </div>
      ),
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
        return <Tag color={colorMap[status] || 'default'}>{status}</Tag>
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: any) => (
        <Popconfirm
          title="Delete"
          description="Are you sure you want to delete this mapping?"
          onConfirm={() => {
            onDelete?.(record.id)
            message.success('Deleted')
          }}
        >
          <Button size="small" danger icon={<Trash2 size={14} />}>
            Delete
          </Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <Table columns={columns} dataSource={mappings} rowKey="id" loading={loading} pagination={{ pageSize: 10 }} />
  )
}
