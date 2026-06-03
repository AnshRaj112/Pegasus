import React from 'react'
import { Card, Table, Checkbox } from 'antd'

interface FileExplorerProps {
  files?: any[]
  selectedFiles?: string[]
  onFileSelect?: (filePath: string, selected: boolean) => void
}

export const FileExplorer: React.FC<FileExplorerProps> = ({ files = [], selectedFiles = [], onFileSelect }) => {
  const columns = [
    {
      title: '',
      dataIndex: 'selected',
      key: 'selected',
      width: 50,
      render: (_: any, record: any) => (
        <Checkbox
          checked={selectedFiles.includes(record.path)}
          onChange={(e) => onFileSelect?.(record.path, e.target.checked)}
        />
      ),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Size',
      dataIndex: 'size',
      key: 'size',
      render: (size: number) => `${(size / 1024 / 1024).toFixed(2)} MB`,
    },
    {
      title: 'Modified',
      dataIndex: 'modified',
      key: 'modified',
      render: (date: string) => new Date(date).toLocaleDateString(),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
    },
  ]

  return (
    <Card title="File Explorer" style={{ marginBottom: '16px' }}>
      <Table columns={columns} dataSource={files} rowKey="path" pagination={{ pageSize: 10 }} />
    </Card>
  )
}
