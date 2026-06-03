import React, { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Card, Button, Input, Radio, Typography, Space, Row, Col, Statistic } from 'antd'
import { ArrowLeftOutlined, SearchOutlined } from '@ant-design/icons'
import ReportSection from '../components/ReportSection'

const { Title, Paragraph, Text } = Typography

export default function DetailedReportPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const result = location?.state?.result ?? null
  const reportTitle = location?.state?.reportTitle ?? null

  const [filterUid, setFilterUid] = useState('')
  const [activeSection, setActiveSection] = useState<'mismatched' | 'missing_in_target' | 'extra_in_target'>('mismatched')

  const samples = useMemo(() => {
    const direct = result?.mismatch_samples ?? []
    if (direct.length > 0) return direct
    const groups = result?.mismatch_sample_groups
    if (!groups) return []
    return [
      ...(groups.missing_in_target ?? []),
      ...(groups.extra_in_target ?? []),
      ...(groups.value_mismatch ?? []),
    ]
  }, [result])

  const filteredSamples = useMemo(() => {
    if (!filterUid.trim()) return samples
    return samples.filter((s: any) =>
      String(s.uid || '').toLowerCase().includes(filterUid.toLowerCase())
    )
  }, [samples, filterUid])

  const valueMismatch = filteredSamples.filter((s: any) => s.mismatch_type === 'value_mismatch')
  const extra = filteredSamples.filter((s: any) => s.mismatch_type === 'extra_in_target')
  const missing = filteredSamples.filter((s: any) => s.mismatch_type === 'missing_in_target')

  const totalMismatched = samples.filter((s: any) => s.mismatch_type === 'value_mismatch').length
  const totalExtra = samples.filter((s: any) => s.mismatch_type === 'extra_in_target').length
  const totalMissing = samples.filter((s: any) => s.mismatch_type === 'missing_in_target').length
  const totalAll = totalMismatched + totalExtra + totalMissing

  const visibleTotalMismatched = valueMismatch.length
  const visibleTotalExtra = extra.length
  const visibleTotalMissing = missing.length
  const visibleTotalAll = visibleTotalMismatched + visibleTotalExtra + visibleTotalMissing

  const activeSamples =
    activeSection === 'missing_in_target'
      ? missing
      : activeSection === 'extra_in_target'
        ? extra
        : valueMismatch

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Back button and page title */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>Detailed Report</Title>
          {reportTitle && (
            <Text code style={{ fontSize: '13px' }}>{reportTitle}</Text>
          )}
        </div>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          Back
        </Button>
      </div>

      {!result ? (
        <Card bordered={false} style={{ textAlign: 'center', padding: '24px' }}>
          <Text type="secondary">No report data received. Return to the validation panel and click View Detailed Report.</Text>
        </Card>
      ) : (
        <>
          {/* Summary stats */}
          <Row gutter={16}>
            <Col span={6}>
              <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                <Statistic title="Total Wrong Entries" value={filterUid ? visibleTotalAll : totalAll} valueStyle={{ fontWeight: 700 }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                <Statistic title="Mismatched" value={filterUid ? visibleTotalMismatched : totalMismatched} valueStyle={{ color: '#d97706', fontWeight: 700 }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                <Statistic title="Missing in Target" value={filterUid ? visibleTotalMissing : totalMissing} valueStyle={{ color: '#ef4444', fontWeight: 700 }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                <Statistic title="Extra in Target" value={filterUid ? visibleTotalExtra : totalExtra} valueStyle={{ color: '#3b82f6', fontWeight: 700 }} />
              </Card>
            </Col>
          </Row>

          {/* Filter UID input */}
          <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <div style={{ fontWeight: 600, marginBottom: '8px', color: '#374151' }}>Filter by UID</div>
            <Input
              placeholder="Enter UID to search..."
              prefix={<SearchOutlined />}
              value={filterUid}
              onChange={(e) => setFilterUid(e.target.value)}
              size="large"
            />
            {filterUid && (
              <Paragraph style={{ marginTop: '8px', color: '#4b5563', margin: 0 }}>
                Showing {filteredSamples.length} results for UID containing "{filterUid}"
              </Paragraph>
            )}
          </Card>

          {/* Section Selection */}
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <Radio.Group
              value={activeSection}
              onChange={(e) => setActiveSection(e.target.value)}
              optionType="button"
              buttonStyle="solid"
              size="large"
            >
              <Radio.Button value="mismatched">
                Mismatched ({filterUid ? visibleTotalMismatched : totalMismatched})
              </Radio.Button>
              <Radio.Button value="missing_in_target">
                Missing ({filterUid ? visibleTotalMissing : totalMissing})
              </Radio.Button>
              <Radio.Button value="extra_in_target">
                Extra ({filterUid ? visibleTotalExtra : totalExtra})
              </Radio.Button>
            </Radio.Group>
          </div>

          {/* Report list */}
          <ReportSection type={activeSection} samples={activeSamples} />
        </>
      )}
    </div>
  )
}
