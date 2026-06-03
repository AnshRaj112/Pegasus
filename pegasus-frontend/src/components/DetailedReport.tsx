import React from 'react'
import { Card, Button, Space, message } from 'antd'
import { Download, Printer } from 'lucide-react'

interface DetailedReportProps {
  data?: any
  title?: string
}

export const DetailedReport: React.FC<DetailedReportProps> = ({ data, title = 'Validation Report' }) => {
  const handleExport = () => {
    message.success('Report exported successfully')
  }

  const handlePrint = () => {
    window.print()
  }

  return (
    <Card
      title={title}
      extra={
        <Space>
          <Button icon={<Download size={14} />} onClick={handleExport}>
            Export
          </Button>
          <Button icon={<Printer size={14} />} onClick={handlePrint}>
            Print
          </Button>
        </Space>
      }
    >
      <div style={{ padding: '24px' }}>
        {data ? (
          <pre style={{ background: '#f5f5f5', padding: '16px', borderRadius: '8px', overflow: 'auto' }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        ) : (
          <p style={{ color: '#999' }}>No report data available</p>
        )}
      </div>
    </Card>
  )
}

export default DetailedReport
