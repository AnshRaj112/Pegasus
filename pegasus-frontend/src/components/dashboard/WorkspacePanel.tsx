import React from 'react'
import { Card, Row, Col, Space } from 'antd'
import { Lock, Plus } from 'lucide-react'

interface WorkspacePanelProps {
  onCreateWorkspace?: () => void
}

export const WorkspacePanel: React.FC<WorkspacePanelProps> = ({ onCreateWorkspace }) => {
  return (
    <Card title="Workspaces">
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12}>
          <Card
            hoverable
            style={{
              border: '1px solid #e5e7eb',
              background: '#f0f5ff',
              borderRadius: '8px',
            }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Lock size={16} color="#52c41a" />
                <span style={{ fontWeight: 600 }}>Global Workspace</span>
              </div>
              <span style={{ fontSize: '12px', color: '#999' }}>System Default</span>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card
            hoverable
            onClick={onCreateWorkspace}
            style={{
              border: '2px dashed #e5e7eb',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: '120px',
              cursor: 'pointer',
            }}
          >
            <div style={{ textAlign: 'center' }}>
              <Plus size={24} color="#999" />
              <p style={{ marginTop: '8px', color: '#999', fontSize: '12px' }}>Add Workspace</p>
            </div>
          </Card>
        </Col>
      </Row>
    </Card>
  )
}
