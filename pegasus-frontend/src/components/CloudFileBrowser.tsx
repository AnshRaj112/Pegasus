import React, { useState, useEffect } from 'react'
import { Card, Input, Button, Select, Form, Row, Col, Table, Spin, Alert, Empty, Tree, Space } from 'antd'
import { Cloud, RefreshCw, ChevronRight } from 'lucide-react'
import { browseCloudPrefix } from '../api/cloudBrowse'

interface CloudFileBrowserProps {
  label?: string
  value?: string
  onChange?: (path: string) => void
  disabled?: boolean
  onConnectionIdChange?: (id: string) => void
  onBucketChange?: (bucket: string) => void
}

interface CloudConnection {
  id: string
  name: string
}

interface CloudFile {
  name: string
  path: string
  size: number
  modified: string
  is_directory: boolean
}

export const CloudFileBrowser: React.FC<CloudFileBrowserProps> = ({
  label = 'Select File',
  value = '',
  onChange,
  disabled = false,
  onConnectionIdChange,
  onBucketChange,
}) => {
  const [form] = Form.useForm()
  const [connectionId, setConnectionId] = useState('')
  const [bucket, setBucket] = useState('')
  const [prefix, setPrefix] = useState('')
  const [files, setFiles] = useState<CloudFile[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [connections, setConnections] = useState<CloudConnection[]>([])
  const [selectedPath, setSelectedPath] = useState(value || '')

  // Mock connections - in production, fetch from API
  useEffect(() => {
    setConnections([
      { id: 'default', name: 'Default GCS Project' },
      { id: 'project-1', name: 'Project 1' },
      { id: 'project-2', name: 'Project 2' },
    ])
  }, [])

  async function handleBrowse() {
    if (!connectionId || !bucket) {
      setError('Please select a connection and bucket')
      return
    }

    setLoading(true)
    setError('')
    try {
      const result = await browseCloudPrefix({
        connectionId,
        bucket,
        prefix: prefix || '',
        fileFormat: 'csv',
      })

      setFiles(result.files || [])
    } catch (err: any) {
      setError(err.message || 'Failed to browse cloud files')
    } finally {
      setLoading(false)
    }
  }

  function handleSelectFile(filePath: string) {
    setSelectedPath(filePath)
    onChange?.(filePath)
  }

  function handlePrefixChange(newPrefix: string) {
    setPrefix(newPrefix)
  }

  function navigateToFolder(folderPath: string) {
    setPrefix(folderPath)
  }

  const columns = [
    {
      title: '',
      dataIndex: 'is_directory',
      key: 'is_directory',
      width: 30,
      render: (isDir: boolean) => (isDir ? '📁' : '📄'),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
      render: (text: string, record: CloudFile) => (
        <span
          style={{
            cursor: record.is_directory ? 'pointer' : 'inherit',
            color: record.is_directory ? '#C41E3A' : 'inherit',
            fontWeight: record.is_directory ? 600 : 400,
          }}
          onClick={() => record.is_directory && navigateToFolder(record.path)}
        >
          {text}
        </span>
      ),
    },
    {
      title: 'Size',
      dataIndex: 'size',
      key: 'size',
      width: 100,
      render: (size: number) => {
        if (!size) return '—'
        return `${(size / 1024 / 1024).toFixed(2)} MB`
      },
    },
    {
      title: 'Modified',
      dataIndex: 'modified',
      key: 'modified',
      width: 120,
      render: (date: string) => new Date(date).toLocaleDateString(),
    },
    {
      title: '',
      key: 'action',
      width: 60,
      render: (_: any, record: CloudFile) =>
        !record.is_directory && (
          <Button
            type="text"
            size="small"
            onClick={() => handleSelectFile(record.path)}
            style={{ color: selectedPath === record.path ? '#C41E3A' : '#8c8c8c' }}
          >
            {selectedPath === record.path ? '✓ Selected' : 'Select'}
          </Button>
        ),
    },
  ]

  return (
    <Card title={<div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Cloud size={16} />{label}</div>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Connection & Bucket Selection */}
        <Row gutter={16}>
          <Col span={12}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ fontSize: '13px', fontWeight: 500 }}>GCS Connection</span>
              <Select
                placeholder="Select connection"
                value={connectionId || undefined}
                disabled={disabled}
                onChange={(val) => {
                  setConnectionId(val)
                  onConnectionIdChange?.(val)
                }}
                options={connections.map((c) => ({ label: c.name, value: c.id }))}
              />
            </div>
          </Col>
          <Col span={12}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ fontSize: '13px', fontWeight: 500 }}>Bucket</span>
              <Input
                placeholder="e.g. my-data-bucket"
                value={bucket}
                disabled={disabled || !connectionId}
                onChange={(e) => {
                  setBucket(e.target.value)
                  onBucketChange?.(e.target.value)
                }}
              />
            </div>
          </Col>
        </Row>

        {/* Prefix Navigation */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 500 }}>Prefix / Path</span>
            <Input
              placeholder="e.g. data/validation/"
              value={prefix}
              disabled={disabled}
              onChange={(e) => handlePrefixChange(e.target.value)}
              onPressEnter={handleBrowse}
            />
          </div>
          <Button
            type="primary"
            icon={<RefreshCw size={16} />}
            loading={loading}
            disabled={disabled || !connectionId || !bucket}
            onClick={handleBrowse}
          >
            Browse
          </Button>
        </div>

        {/* File List */}
        {error && <Alert message={error} type="error" showIcon />}

        {loading && (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <Spin tip="Loading files..." />
          </div>
        )}

        {!loading && files.length === 0 && !error && (
          <Empty description="No files found" style={{ marginTop: '20px' }} />
        )}

        {!loading && files.length > 0 && (
          <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: '16px' }}>
            <Table
              columns={columns}
              dataSource={files.map((f, i) => ({ ...f, key: i }))}
              pagination={{ pageSize: 10 }}
              size="small"
              bordered={false}
            />
          </div>
        )}

        {/* Selected File Display */}
        {selectedPath && (
          <div
            style={{
              background: 'rgba(196, 30, 58, 0.05)',
              border: '1px solid rgba(196, 30, 58, 0.2)',
              borderRadius: '6px',
              padding: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span style={{ fontSize: '12px', color: '#7F8C8D' }}>Selected:</span>
            <code style={{ flex: 1, fontSize: '12px', color: '#C41E3A', fontWeight: 500, wordBreak: 'break-all' }}>
              gs://{bucket}/{selectedPath}
            </code>
          </div>
        )}
      </div>
    </Card>
  )
}
