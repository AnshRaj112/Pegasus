import React from 'react'
import { Table, Tag } from 'antd'

interface MismatchSampleRowsProps {
  rows?: any[]
  title?: string
}

export const MismatchSampleRows: React.FC<MismatchSampleRowsProps> = ({
  rows = [],
  title = 'Mismatch Sample Rows',
}) => {
  const columns = [
    {
      title: 'Row ID',
      dataIndex: 'row_id',
      key: 'row_id',
    },
    {
      title: 'Column',
      dataIndex: 'column',
      key: 'column',
    },
    {
      title: 'Source Value',
      dataIndex: 'source_value',
      key: 'source_value',
      render: (value: any) => <code>{JSON.stringify(value)}</code>,
    },
    {
      title: 'Target Value',
      dataIndex: 'target_value',
      key: 'target_value',
      render: (value: any) => <code>{JSON.stringify(value)}</code>,
    },
    {
      title: 'Match Status',
      dataIndex: 'match_status',
      key: 'match_status',
      render: (status: string) => (
        <Tag color={status === 'mismatch' ? 'red' : 'green'}>{status}</Tag>
      ),
    },
  ]

  return (
    <div>
      <h4>{title}</h4>
      <Table columns={columns} dataSource={rows} rowKey="id" pagination={{ pageSize: 10 }} size="small" />
    </div>
  )
}
