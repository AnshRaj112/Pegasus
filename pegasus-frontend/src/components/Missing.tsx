import React from 'react'
import { Table, Card } from 'antd'

export const Missing: React.FC<{ data?: any[] }> = ({ data = [] }) => {
  const columns = [
    {
      title: 'Row ID',
      dataIndex: 'row_id',
      key: 'row_id',
    },
    {
      title: 'Missing In',
      dataIndex: 'missing_in',
      key: 'missing_in',
    },
  ]

  return (
    <Card title="Missing Records">
      <Table columns={columns} dataSource={data} rowKey="row_id" pagination={{ pageSize: 10 }} />
    </Card>
  )
}

export default Missing
