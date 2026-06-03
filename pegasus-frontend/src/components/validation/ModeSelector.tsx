import React from 'react'
import { Select, Card } from 'antd'

interface ModeSelectorProps {
  value?: string
  onChange?: (mode: string) => void
}

export const ModeSelector: React.FC<ModeSelectorProps> = ({ value, onChange }) => {
  return (
    <Card title="Execution Mode" style={{ marginBottom: '16px' }}>
      <Select
        value={value || 'single-to-single'}
        onChange={onChange}
        style={{ width: '100%' }}
        options={[
          { label: 'Single to Single', value: 'single-to-single' },
          { label: 'Single to Many', value: 'single-to-many' },
          { label: 'Many to Single', value: 'many-to-single' },
          { label: 'Many to Many', value: 'many-to-many' },
        ]}
      />
    </Card>
  )
}
