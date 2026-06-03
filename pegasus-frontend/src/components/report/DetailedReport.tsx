import React from 'react'
import { Card, Descriptions, Table, Button, Space } from 'antd'
import { Eye } from 'lucide-react'

interface DetailedReportProps {
  reportData?: any
  onViewDetails?: () => void
}

export const DetailedReport: React.FC<DetailedReportProps> = ({ reportData, onViewDetails }) => {
  const items = [
    {
      key: '1',
      label: 'Run ID',
      children: reportData?.run_id || '-',
    },
    {
      key: '2',
      label: 'Source File',
      children: reportData?.source_filename || '-',
    },
    {
      key: '3',
      label: 'Target File',
      children: reportData?.target_filename || '-',
    },
    {
      key: '4',
      label: 'Status',
      children: reportData?.status || '-',
    },
    {
      key: '5',
      label: 'Total Duration',
      children: `${reportData?.durations?.total_seconds || 0}s`,
    },
  ]

  return (
    <div style={{ padding: '24px' }}>
      <Card title="Validation Report">
        <Descriptions items={items} bordered column={2} />
        <div style={{ marginTop: '24px' }}>
          <Button type="primary" icon={<Eye size={14} />} onClick={onViewDetails}>
            View Full Report
          </Button>
        </div>
      </Card>
    </div>
  )
}
