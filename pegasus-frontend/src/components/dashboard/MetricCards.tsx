import React from 'react'
import { Card, Row, Col, Statistic } from 'antd'
import { CheckCircle, XCircle, FileText, Activity } from 'lucide-react'

interface MetricCardsProps {
  passCount: number
  failCount: number
  totalFilesValidated: number
  currentlyRunning: number
}

export const MetricCards: React.FC<MetricCardsProps> = ({
  passCount,
  failCount,
  totalFilesValidated,
  currentlyRunning,
}) => {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} sm={12} lg={6}>
        <Card>
          <Statistic
            title="Passed"
            value={passCount}
            prefix={<CheckCircle size={16} color="#52c41a" />}
            valueStyle={{ color: '#52c41a' }}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card>
          <Statistic
            title="Failed"
            value={failCount}
            prefix={<XCircle size={16} color="#ba1a1a" />}
            valueStyle={{ color: '#ba1a1a' }}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card>
          <Statistic
            title="Total Files Validated"
            value={totalFilesValidated}
            prefix={<FileText size={16} color="#1677ff" />}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card>
          <Statistic
            title="Currently Running"
            value={currentlyRunning}
            prefix={<Activity size={16} color="#faad14" />}
            valueStyle={{ color: '#faad14' }}
          />
        </Card>
      </Col>
    </Row>
  )
}
