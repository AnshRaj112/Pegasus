import React, { useState } from 'react'
import { Card, Button, Row, Col, Tag, Space, Modal, Form, Select, Input, message } from 'antd'
import { Plus, TestTube, Cloud } from 'lucide-react'
import type { StoreBucket } from '../../types'

export default function ConfigureStorePage() {
  const [buckets, setBuckets] = useState<StoreBucket[]>([
    {
      bucket_name: 'default-staging',
      provider: 'gcs',
      connection_status: 'connected',
      bucket_path: 'gs://default-staging',
      last_sync: new Date().toISOString(),
      region: 'us-central1',
    },
  ])
  const [isModalVisible, setIsModalVisible] = useState(false)
  const [form] = Form.useForm()

  const handleAddBucket = async (values: any) => {
    try {
      const newBucket: StoreBucket = {
        bucket_name: values.bucket_name,
        provider: values.provider,
        connection_status: 'untested',
        bucket_path: values.bucket_path,
        region: values.region,
      }
      setBuckets([...buckets, newBucket])
      message.success('Storage bucket added')
      form.resetFields()
      setIsModalVisible(false)
    } catch (error) {
      message.error('Failed to add bucket')
    }
  }

  const handleTestConnection = (name: string) => {
    Modal.confirm({
      title: 'Test Connection',
      content: `Testing connection to ${name}...`,
      okText: 'Close',
      cancelButtonProps: { style: { display: 'none' } },
      onOk() {
        message.success('Connection test passed')
      },
    })
  }

  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'gcs':
        return '☁️'
      case 's3':
        return '📦'
      case 'local':
        return '💾'
      default:
        return '📁'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected':
        return 'green'
      case 'failed':
        return 'red'
      default:
        return 'gold'
    }
  }

  return (
    <div style={{ padding: '24px' }}>
      <Card title="Storage Configuration">
        <Row gutter={[16, 16]}>
          {buckets.map(bucket => (
            <Col key={bucket.bucket_name} xs={24} sm={12} lg={8}>
              <Card
                hoverable
                style={{
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  height: '100%',
                }}
              >
                <Space direction="vertical" style={{ width: '100%' }} size="large">
                  <div>
                    <div style={{ fontSize: '24px', marginBottom: '8px' }}>
                      {getProviderIcon(bucket.provider)}
                    </div>
                    <h4 style={{ margin: '0 0 4px 0' }}>{bucket.bucket_name}</h4>
                    <Tag color="blue">{bucket.provider.toUpperCase()}</Tag>
                    <Tag color={getStatusColor(bucket.connection_status)}>
                      {bucket.connection_status}
                    </Tag>
                  </div>
                  <div style={{ fontSize: '12px', color: '#666' }}>
                    <p style={{ margin: '0' }}><strong>Path:</strong></p>
                    <code style={{ fontSize: '11px' }}>{bucket.bucket_path}</code>
                  </div>
                  {bucket.region && (
                    <div style={{ fontSize: '12px', color: '#666' }}>
                      <strong>Region:</strong> {bucket.region}
                    </div>
                  )}
                  <Button
                    type="primary"
                    size="small"
                    icon={<TestTube size={14} />}
                    onClick={() => handleTestConnection(bucket.bucket_name)}
                  >
                    Test Connection
                  </Button>
                </Space>
              </Card>
            </Col>
          ))}
          <Col xs={24} sm={12} lg={8}>
            <Card
              hoverable
              onClick={() => setIsModalVisible(true)}
              style={{
                border: '2px dashed #e5e7eb',
                borderRadius: '8px',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <Plus size={32} color="#bfbfbf" />
                <p style={{ marginTop: '12px', color: '#999' }}>Add Storage Bucket</p>
              </div>
            </Card>
          </Col>
        </Row>
      </Card>

      <Modal
        title="Add Storage Bucket"
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false)
          form.resetFields()
        }}
        onOk={() => form.submit()}
      >
        <Form form={form} onFinish={handleAddBucket} layout="vertical">
          <Form.Item
            label="Bucket Name"
            name="bucket_name"
            rules={[{ required: true, message: 'Please enter bucket name' }]}
          >
            <Input placeholder="e.g., my-staging-bucket" />
          </Form.Item>
          <Form.Item
            label="Provider"
            name="provider"
            rules={[{ required: true, message: 'Please select provider' }]}
          >
            <Select placeholder="Select provider">
              <Select.Option value="gcs">Google Cloud Storage</Select.Option>
              <Select.Option value="s3">Amazon S3</Select.Option>
              <Select.Option value="local">Local</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            label="Bucket Path"
            name="bucket_path"
            rules={[{ required: true, message: 'Please enter bucket path' }]}
          >
            <Input placeholder="e.g., gs://my-bucket or s3://my-bucket" />
          </Form.Item>
          <Form.Item label="Region" name="region">
            <Input placeholder="e.g., us-central1" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
