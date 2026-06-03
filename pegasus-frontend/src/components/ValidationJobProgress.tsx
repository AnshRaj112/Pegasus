import React from 'react'
import { Card, Progress, Space, Spin } from 'antd'

interface ValidationJobProgressProps {
  jobId?: string
  progress?: number
  status?: string
  message?: string
}

export const ValidationJobProgress: React.FC<ValidationJobProgressProps> = ({
  jobId,
  progress = 0,
  status = 'running',
  message: msg,
}) => {
  return (
    <Card title="Validation Progress">
      <Space direction="vertical" style={{ width: '100%' }}>
        {status === 'running' && <Spin />}
        <Progress percent={progress} status={status as any} />
        {msg && <p>{msg}</p>}
      </Space>
    </Card>
  )
}

export default ValidationJobProgress
