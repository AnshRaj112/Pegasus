import React from 'react'
import { Table, Card } from 'antd'

export const Mismatched: React.FC<{ data?: any[] }> = ({ data = [] }) => {
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
    },
    {
      title: 'Target Value',
      dataIndex: 'target_value',
      key: 'target_value',
    },
  ]

  return (
    <Card title="Mismatched Records">
      <Table columns={columns} dataSource={data} rowKey="id" pagination={{ pageSize: 10 }} />
    </Card>
  )
}

export default Mismatched
