import React from 'react'
import { Card } from 'antd'

export const ValidationPanel: React.FC<{ data?: any }> = ({ data }) => {
  return (
    <Card title="Validation Panel">
      <p>Validation details and status</p>
    </Card>
  )
}

export default ValidationPanel
