import React from 'react'
import { Alert } from 'antd'
import { AlertCircle } from 'lucide-react'

interface BackendStatusBannerProps {
  isHealthy?: boolean
  message?: string
}

export const BackendStatusBanner: React.FC<BackendStatusBannerProps> = ({
  isHealthy = true,
  message: msg = 'Backend service is running normally',
}) => {
  if (isHealthy) return null

  return (
    <Alert
      message="Backend Connection Error"
      description={msg}
      type="error"
      showIcon
      icon={<AlertCircle size={16} />}
      style={{ marginBottom: '16px' }}
    />
  )
}
