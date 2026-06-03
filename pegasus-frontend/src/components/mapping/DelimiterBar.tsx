import React from 'react'
import { Card, Input, Select, Tag } from 'antd'

interface DelimiterBarProps {
  detectedDelimiter?: string
  onDelimiterChange?: (delimiter: string) => void
}

export const DelimiterBar: React.FC<DelimiterBarProps> = ({ detectedDelimiter = ',', onDelimiterChange }) => {
  return (
    <Card
      title="System Configuration"
      style={{ marginBottom: '16px', background: '#f9fafb' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div>
          <span style={{ fontWeight: 600 }}>System Auto-Detected Delimiter:</span>
          <Tag color="blue" style={{ marginLeft: '8px' }}>
            <code>{detectedDelimiter}</code>
          </Tag>
        </div>
        <Select
          style={{ minWidth: '200px' }}
          value={detectedDelimiter}
          onChange={onDelimiterChange}
          options={[
            { label: 'Comma (,)', value: ',' },
            { label: 'Semicolon (;)', value: ';' },
            { label: 'Pipe (|)', value: '|' },
            { label: 'Tab', value: '\t' },
            { label: 'Space', value: ' ' },
          ]}
        />
      </div>
    </Card>
  )
}
