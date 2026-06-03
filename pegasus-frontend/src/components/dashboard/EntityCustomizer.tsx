import React from 'react'
import { Card, Select, Input, Button, Space, Switch } from 'antd'
import { Search, Plus } from 'lucide-react'

interface EntityCustomizerProps {
  onEntitySelect?: (entity: string) => void
  onCreateDashboard?: () => void
}

export const EntityCustomizer: React.FC<EntityCustomizerProps> = ({
  onEntitySelect,
  onCreateDashboard,
}) => {
  return (
    <Card title="Entity Customizer">
      <Space direction="vertical" style={{ width: '100%' }}>
        <div>
          <label style={{ fontSize: '12px', fontWeight: 600, color: '#666' }}>
            Search Entity
          </label>
          <Input
            placeholder="Search entities..."
            prefix={<Search size={14} />}
            style={{ marginTop: '8px' }}
          />
        </div>
        <div>
          <label style={{ fontSize: '12px', fontWeight: 600, color: '#666' }}>
            Select Entity
          </label>
          <Select
            placeholder="Choose an entity..."
            style={{ width: '100%', marginTop: '8px' }}
            onChange={onEntitySelect}
            options={[
              { label: 'Customer', value: 'customer' },
              { label: 'Order', value: 'order' },
              { label: 'Product', value: 'product' },
            ]}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: '#666' }}>
            Incremental Tracking
          </label>
          <Switch />
        </div>
        <Button
          type="primary"
          block
          icon={<Plus size={14} />}
          onClick={onCreateDashboard}
        >
          Create Micro-Dashboard
        </Button>
      </Space>
    </Card>
  )
}
