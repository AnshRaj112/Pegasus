import React from 'react'
import { Button, Space } from 'antd'
import { CheckCircle, Play } from 'lucide-react'

interface MappingFooterProps {
  onMap?: () => void
  onMapAndValidate?: () => void
  loading?: boolean
}

export const MappingFooter: React.FC<MappingFooterProps> = ({ onMap, onMapAndValidate, loading }) => {
  return (
    <Space style={{ marginTop: '24px', justifyContent: 'flex-end', width: '100%' }}>
      <Button onClick={onMap} loading={loading}>
        <CheckCircle size={14} /> Map
      </Button>
      <Button type="primary" onClick={onMapAndValidate} loading={loading}>
        <Play size={14} /> Map and Validate
      </Button>
    </Space>
  )
}
