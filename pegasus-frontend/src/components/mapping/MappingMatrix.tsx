import React from 'react'
import { Card, Table, Input, Select, Space, Tag } from 'antd'
import { Search } from 'lucide-react'

interface MappingMatrixProps {
  columns?: any[]
  onMappingChange?: (sourceCol: string, targetCols: string[]) => void
}

export const MappingMatrix: React.FC<MappingMatrixProps> = ({ columns = [], onMappingChange }) => {
  const [searchText, setSearchText] = React.useState('')

  const dataTypes = ['STRING', 'INTEGER', 'FLOAT', 'DATETIME', 'BOOLEAN']

  const tableColumns = [
    {
      title: 'Source Column',
      dataIndex: 'source_column',
      key: 'source_column',
      width: 200,
    },
    {
      title: 'Data Type',
      dataIndex: 'data_type',
      key: 'data_type',
      render: (type: string) => (
        <Tag color="blue">{type || 'STRING'}</Tag>
      ),
    },
    {
      title: 'Target Mapping',
      dataIndex: 'target_column',
      key: 'target_mapping',
      render: (targets: string[]) => (
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          value={targets || []}
          options={[
            { label: 'target_col_1', value: 'target_col_1' },
            { label: 'target_col_2', value: 'target_col_2' },
            { label: 'target_col_3', value: 'target_col_3' },
          ]}
        />
      ),
    },
    {
      title: 'Preview Value',
      dataIndex: 'preview',
      key: 'preview',
      render: (value: string) => (
        <code style={{ fontSize: '12px', background: '#f5f5f5', padding: '2px 6px', borderRadius: '4px' }}>
          {value || '-'}
        </code>
      ),
    },
  ]

  const filteredColumns = columns.filter(col =>
    col.source_column.toLowerCase().includes(searchText.toLowerCase())
  )

  return (
    <Card title="Column Mapping">
      <Space direction="vertical" style={{ width: '100%' }}>
        <Input
          placeholder="Search columns..."
          prefix={<Search size={14} />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
        <Table
          columns={tableColumns}
          dataSource={filteredColumns}
          rowKey="source_column"
          pagination={{ pageSize: 15 }}
          scroll={{ y: 550 }}
          size="small"
        />
      </Space>
    </Card>
  )
}
