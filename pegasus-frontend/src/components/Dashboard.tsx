import React from 'react'
import { Card, Row, Col, Statistic } from 'antd'
import { CheckCircle, XCircle } from 'lucide-react'

// This is imported by DashboardPage - simple stats display
export const Dashboard: React.FC<{ data?: any }> = ({ data }) => {
  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Passed"
              value={data?.passed || 0}
              prefix={<CheckCircle size={16} color="#52c41a" />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Failed"
              value={data?.failed || 0}
              prefix={<XCircle size={16} color="#ba1a1a" />}
              valueStyle={{ color: '#ba1a1a' }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard
