import React from 'react'
import { Button, Space } from 'antd'
import { ArrowRight } from 'lucide-react'

interface ValidationFooterProps {
  onProceed?: () => void
  loading?: boolean
}

export const ValidationFooter: React.FC<ValidationFooterProps> = ({ onProceed, loading }) => {
  return (
    <Space style={{ marginTop: '24px', justifyContent: 'flex-end', width: '100%' }}>
      <Button
        type="primary"
        size="large"
        icon={<ArrowRight size={16} />}
        onClick={onProceed}
        loading={loading}
      >
        Proceed to Mapping
      </Button>
    </Space>
  )
}
