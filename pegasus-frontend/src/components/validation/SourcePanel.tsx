import React from 'react'
import { Card, Radio, Space } from 'antd'
import { Cloud, HardDrive } from 'lucide-react'

interface SourcePanelProps {
  sourceType?: 'cloud' | 'local'
  onSourceTypeChange?: (type: 'cloud' | 'local') => void
}

export const SourcePanel: React.FC<SourcePanelProps> = ({ sourceType = 'local', onSourceTypeChange }) => {
  return (
    <Card title="Select Source" style={{ marginBottom: '16px' }}>
      <Radio.Group value={sourceType} onChange={(e) => onSourceTypeChange?.(e.target.value)}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Radio value="cloud">
            <Space>
              <Cloud size={16} />
              <span>GCS Cloud Storage</span>
            </Space>
          </Radio>
          <Radio value="local">
            <Space>
              <HardDrive size={16} />
              <span>Local Device</span>
            </Space>
          </Radio>
        </Space>
      </Radio.Group>
    </Card>
  )
}
