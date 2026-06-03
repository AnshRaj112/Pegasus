import React, { useState, useEffect } from 'react'
import { Card, Button, Table, Modal, Form, Input, message, Space, Badge, Tag } from 'antd'
import { Plus, Trash2, Lock } from 'lucide-react'
import type { Workspace } from '../../types'

export default function WorkspaceManagementPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([
    {
      workspace_name: 'Global Workspace',
      created_at: '2024-01-01T00:00:00Z',
      active_users: 5,
      status: 'active',
    },
  ])
  const [isModalVisible, setIsModalVisible] = useState(false)
  const [form] = Form.useForm()

  const handleCreateWorkspace = async (values: any) => {
    try {
      const newWorkspace: Workspace = {
        workspace_name: values.workspace_name,
        created_at: new Date().toISOString(),
        active_users: 1,
        status: 'active',
      }
      setWorkspaces([...workspaces, newWorkspace])
      message.success('Workspace created successfully')
      form.resetFields()
      setIsModalVisible(false)
    } catch (error) {
      message.error('Failed to create workspace')
    }
  }

  const handleDelete = (name: string) => {
    if (name === 'Global Workspace') {
      message.error('Cannot delete Global Workspace')
      return
    }
    Modal.confirm({
      title: 'Delete Workspace',
      content: `Are you sure you want to delete "${name}"?`,
      okText: 'Delete',
      okType: 'danger',
      onOk() {
        setWorkspaces(workspaces.filter(w => w.workspace_name !== name))
        message.success('Workspace deleted')
      },
    })
  }

  const columns = [
    {
      title: 'Workspace Name',
      dataIndex: 'workspace_name',
      key: 'workspace_name',
      render: (text: string) => (
        <Space>
          {text === 'Global Workspace' && <Lock size={14} color="#52c41a" />}
          <span>{text}</span>
          {text === 'Global Workspace' && <Tag color="green">System Default</Tag>}
        </Space>
      ),
    },
    {
      title: 'Created Date',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleDateString(),
    },
    {
      title: 'Active Users',
      dataIndex: 'active_users',
      key: 'active_users',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Badge status={status === 'active' ? 'success' : 'default'} text={status} />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Workspace) => (
        <Button
          danger
          size="small"
          icon={<Trash2 size={14} />}
          onClick={() => handleDelete(record.workspace_name)}
          disabled={record.workspace_name === 'Global Workspace'}
        >
          Delete
        </Button>
      ),
    },
  ]

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title="Workspace Management"
        extra={
          <Button type="primary" icon={<Plus size={16} />} onClick={() => setIsModalVisible(true)}>
            Create New Workspace
          </Button>
        }
      >
        <Table columns={columns} dataSource={workspaces} rowKey="workspace_name" />
      </Card>

      <Modal
        title="Create New Workspace"
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false)
          form.resetFields()
        }}
        onOk={() => form.submit()}
      >
        <Form form={form} onFinish={handleCreateWorkspace} layout="vertical">
          <Form.Item
            label="Workspace Name"
            name="workspace_name"
            rules={[{ required: true, message: 'Please enter workspace name' }]}
          >
            <Input placeholder="Enter workspace name" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
