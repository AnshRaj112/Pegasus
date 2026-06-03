import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Row, Col, Statistic, Table, Timeline, Button, Space, Typography, Tag, Progress, Badge } from 'antd'
import { ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined, SyncOutlined } from '@ant-design/icons'
import { fetchValidationHistory } from '../api/validationHistory'

const { Title, Paragraph, Text } = Typography

export default function InternalDashboardPage() {
  const { entityId } = useParams<{ entityId: string }>()
  const navigate = useNavigate()
  const [historyRuns, setHistoryRuns] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchValidationHistory({ limit: 100, offset: 0 })
      .then((data) => {
        if (cancelled) return
        const items = Array.isArray(data.items) ? data.items : []
        // Filter runs matching this entity if possible, else keep runs
        const filtered = items.filter((item: any) => {
          const nameMatch = String(item.source_filename ?? '').toLowerCase() + ' ' + String(item.target_filename ?? '').toLowerCase()
          return nameMatch.includes(String(entityId ?? '').toLowerCase())
        })
        setHistoryRuns(filtered.length > 0 ? filtered : items.slice(0, 10))
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [entityId])

  const stats = {
    activeValidations: historyRuns.filter(r => r.status === 'running' || r.status === 'queued').length,
    passedCount: historyRuns.filter(r => r.status === 'success' || r.is_match === true).length,
    failedCount: historyRuns.filter(r => r.status === 'failed' || r.is_match === false).length,
    totalCount: historyRuns.length
  }

  const integrityScore = stats.totalCount > 0 ? Math.round((stats.passedCount / stats.totalCount) * 100) : 100

  const timelineItems = historyRuns.slice(0, 6).map((run, index) => {
    const isPassed = run.is_match === true || run.status === 'success'
    const color = isPassed ? 'green' : run.status === 'running' ? 'blue' : 'red'
    const dot = isPassed ? <CheckCircleOutlined /> : run.status === 'running' ? <SyncOutlined spin /> : <CloseCircleOutlined />

    return {
      dot,
      color,
      children: (
        <div>
          <Text strong style={{ fontSize: '13px' }}>
            {run.source_filename || 'Unknown File'} vs {run.target_filename || 'Unknown File'}
          </Text>
          <div>
            <Tag color={color}>{run.status?.toUpperCase() || 'COMPLETED'}</Tag>
            <Text type="secondary" style={{ fontSize: '11px' }}>
              {run.completed_at ? new Date(run.completed_at).toLocaleString() : 'Just now'}
            </Text>
          </div>
        </div>
      )
    }
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Title & Back Button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>Entity Drilldown: {entityId}</Title>
          <Paragraph type="secondary" style={{ margin: '4px 0 0 0' }}>
            Granular analysis and historical runs mapping to {entityId} pattern.
          </Paragraph>
        </div>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/dashboard')}>
          Back to Dashboard
        </Button>
      </div>

      {/* Metrics Row */}
      <Row gutter={16}>
        <Col span={6}>
          <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <Statistic
              title="Active Validations"
              value={stats.activeValidations}
              valueStyle={{ color: '#1677ff', fontWeight: 700 }}
              prefix={<SyncOutlined spin={stats.activeValidations > 0} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <Text type="secondary" style={{ fontSize: '14px' }}>Global Integrity Score</Text>
                <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px' }}>{integrityScore}%</div>
              </div>
              <Progress type="circle" percent={integrityScore} size={44} strokeColor={integrityScore > 80 ? '#52c41a' : '#faad14'} />
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <Statistic
              title="Passed Matches"
              value={stats.passedCount}
              valueStyle={{ color: '#52c41a', fontWeight: 700 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <Statistic
              title="Failed Runs"
              value={stats.failedCount}
              valueStyle={{ color: '#ff4d4f', fontWeight: 700 }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={24}>
        {/* Left Column: Active Validation Sets */}
        <Col span={16}>
          <Card title="Active & Historical Validation Runs" bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <Table
              dataSource={historyRuns}
              loading={loading}
              rowKey={(record) => record.run_id}
              columns={[
                {
                  title: 'Source File',
                  dataIndex: 'source_filename',
                  key: 'source_filename',
                  render: (text, row) => (
                    <div>
                      <Text strong style={{ fontSize: '13px' }}>{text || '—'}</Text>
                      <div style={{ fontSize: '11px', color: '#8c8c8c' }}>{row.source_path || '—'}</div>
                    </div>
                  )
                },
                {
                  title: 'Target File',
                  dataIndex: 'target_filename',
                  key: 'target_filename',
                  render: (text, row) => (
                    <div>
                      <Text strong style={{ fontSize: '13px' }}>{text || '—'}</Text>
                      <div style={{ fontSize: '11px', color: '#8c8c8c' }}>{row.target_path || '—'}</div>
                    </div>
                  )
                },
                {
                  title: 'Status',
                  dataIndex: 'status',
                  key: 'status',
                  render: (text, row) => {
                    const isPassed = row.is_match === true || text === 'success'
                    return (
                      <Tag color={isPassed ? 'green' : text === 'running' ? 'blue' : 'red'}>
                        {isPassed ? 'PASSED' : String(text || 'FAILED').toUpperCase()}
                      </Tag>
                    )
                  }
                },
                {
                  title: 'Mismatches',
                  dataIndex: 'mismatch_count',
                  key: 'mismatch_count',
                  render: (val) => val != null ? <Badge count={val} overflowCount={99999} style={{ backgroundColor: val > 0 ? '#ff4d4f' : '#52c41a' }} /> : '—'
                },
                {
                  title: 'Actions',
                  key: 'actions',
                  render: (_, row) => (
                    <Button
                      size="small"
                      onClick={() => navigate('/report', { state: { result: row } })}
                    >
                      View Report
                    </Button>
                  )
                }
              ]}
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </Col>

        {/* Right Column: Activity Timeline */}
        <Col span={8}>
          <Card title="Recent Activity Feed" bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            {timelineItems.length > 0 ? (
              <Timeline items={timelineItems} />
            ) : (
              <div style={{ textAlign: 'center', padding: '24px 0', color: '#bfbfbf' }}>
                No recent activity for this entity
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
