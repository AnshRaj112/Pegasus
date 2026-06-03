import React from 'react'
import { Card } from 'antd'

export const Extra: React.FC<{ data?: any }> = ({ data }) => {
  return (
    <Card title="Extra Information">
      <p>Additional data and statistics</p>
      {data && <pre>{JSON.stringify(data, null, 2)}</pre>}
    </Card>
  )
}

export default Extra
