import { useMemo, useState } from 'react'
import { Button, Card, Col, Empty, Input, Row, Segmented, Space, Statistic, Typography } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import ReportSection from './ReportSection'

export default function DetailedReport() {
  const location = useLocation()
  const navigate = useNavigate()
  const result = location?.state?.result ?? null
  const reportTitle = location?.state?.reportTitle ?? null
  const [filterUid, setFilterUid] = useState('')
  const [activeSection, setActiveSection] = useState('mismatched')

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
    return samples.filter((sample: any) => sample.uid?.toLowerCase().includes(filterUid.toLowerCase()))
  }, [samples, filterUid])

  const valueMismatch = filteredSamples.filter((sample: any) => sample.mismatch_type === 'value_mismatch')
  const extra = filteredSamples.filter((sample: any) => sample.mismatch_type === 'extra_in_target')
  const missing = filteredSamples.filter((sample: any) => sample.mismatch_type === 'missing_in_target')
  const totalMismatched = samples.filter((sample: any) => sample.mismatch_type === 'value_mismatch').length
  const totalExtra = samples.filter((sample: any) => sample.mismatch_type === 'extra_in_target').length
  const totalMissing = samples.filter((sample: any) => sample.mismatch_type === 'missing_in_target').length
  const totalAll = totalMismatched + totalExtra + totalMissing
  const visibleTotalMismatched = valueMismatch.length
  const visibleTotalExtra = extra.length
  const visibleTotalMissing = missing.length
  const visibleTotalAll = visibleTotalMismatched + visibleTotalExtra + visibleTotalMissing

  const sections = [
    { key: 'mismatched', label: 'Mismatched', count: valueMismatch.length },
    { key: 'missing_in_target', label: 'Missing', count: missing.length },
    { key: 'extra_in_target', label: 'Extra', count: extra.length },
  ]

  const activeSamples =
    activeSection === 'missing_in_target' ? missing : activeSection === 'extra_in_target' ? extra : valueMismatch

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #fffdef 0%, #f1f1f1 100%)', padding: 24 }}>
      <div style={{ maxWidth: 1440, margin: '0 auto' }}>
        <Card style={{ marginBottom: 24 }}>
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <div>
                <Typography.Text type="secondary">Validation output</Typography.Text>
                <Typography.Title level={2} style={{ marginTop: 8, marginBottom: 0 }}>Detailed Report</Typography.Title>
                {reportTitle ? <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }} code>{reportTitle}</Typography.Paragraph> : null}
              </div>
              <Button onClick={() => navigate(-1)}>Back</Button>
            </Space>
            <Typography.Paragraph type="secondary" style={{ maxWidth: 900, marginBottom: 0 }}>
              Review mismatched, missing, and extra records in separate sections with unified cards and page-by-page navigation.
            </Typography.Paragraph>
          </Space>
        </Card>

        {!result ? (
          <Empty description="No report data received. Return to the validation panel and click View Detailed Report." />
        ) : (
          <Space direction="vertical" size={24} style={{ width: '100%' }}>
            <Row gutter={[16, 16]}>
              <Col xs={24} sm={12} lg={6}><Card><Statistic title="Total Wrong Entries" value={filterUid ? visibleTotalAll : totalAll} /></Card></Col>
              <Col xs={24} sm={12} lg={6}><Card><Statistic title="Mismatched" value={filterUid ? visibleTotalMismatched : totalMismatched} valueStyle={{ color: '#d46b08' }} /></Card></Col>
              <Col xs={24} sm={12} lg={6}><Card><Statistic title="Missing in Target" value={filterUid ? visibleTotalMissing : totalMissing} valueStyle={{ color: '#d48806' }} /></Card></Col>
              <Col xs={24} sm={12} lg={6}><Card><Statistic title="Extra in Target" value={filterUid ? visibleTotalExtra : totalExtra} valueStyle={{ color: '#1677ff' }} /></Card></Col>
            </Row>

            <Card title="Filter by UID">
              <Input value={filterUid} onChange={(e) => setFilterUid(e.target.value)} placeholder="Enter UID to search..." />
              {filterUid ? <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>Showing {filteredSamples.length} results for UID containing "{filterUid}"</Typography.Paragraph> : null}
            </Card>

            <Segmented
              block
              value={activeSection}
              onChange={(value) => setActiveSection(String(value))}
              options={sections.map((section) => ({ label: `${section.label} (${section.count})`, value: section.key }))}
            />

            <ReportSection type={activeSection} samples={activeSamples} />
          </Space>
        )}
      </div>
    </div>
  )
}