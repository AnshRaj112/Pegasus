import React from 'react'
import { Table } from 'antd'

interface ReportSectionProps {
  title: string
  data: any[]
  columns: any[]
}

export const ReportSection: React.FC<ReportSectionProps> = ({ title, data, columns }) => {
  return (
    <div style={{ marginBottom: '24px' }}>
      <h3 style={{ marginBottom: '16px' }}>{title}</h3>
      <Table columns={columns} dataSource={data} rowKey="id" pagination={{ pageSize: 10 }} />
    </div>
  )
}
