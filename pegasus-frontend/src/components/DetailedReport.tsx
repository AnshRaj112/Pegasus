import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Col, Empty, Input, Row, Segmented, Space, Statistic, Typography } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  fetchValidationHistoryMismatches,
  normalizeMismatchRow,
} from '../api/validationHistory'
import ReportSection from './ReportSection'

const DETAILED_REPORT_MISMATCH_PAGE_SIZE = 5000

function buildMismatchSampleGroups(samples: any[]) {
  const grouped = {
    missing_in_target: [],
    extra_in_target: [],
    value_mismatch: [],
  }

  for (const sample of samples) {
    if (grouped[sample.mismatch_type as keyof typeof grouped]) {
      grouped[sample.mismatch_type as keyof typeof grouped].push(sample)
    }
  }

  return grouped
}

function resolveMismatchCounts(reportResult: any) {
  const counts = reportResult?.mismatch_counts ?? {}
  return {
    missing_in_target: Number(counts.missing_in_target ?? 0),
    extra_in_target: Number(counts.extra_in_target ?? 0),
    value_mismatch: Number(
      counts.value_mismatch
      ?? reportResult?.summary?.value_mismatch_records
      ?? reportResult?.value_mismatch_records
      ?? 0,
    ),
  }
}

function sectionMismatchType(section: string) {
  return section === 'mismatched' ? 'value_mismatch' : section
}

async function fetchAllHistoryMismatches(runId: string, mismatchType?: string) {
  const items: any[] = []
  let offset = 0
  let total = 0

  while (true) {
    const page = await fetchValidationHistoryMismatches(runId, {
      limit: DETAILED_REPORT_MISMATCH_PAGE_SIZE,
      offset,
      mismatchType,
    })
    const pageItems = Array.isArray(page.items) ? page.items.map(normalizeMismatchRow) : []
    total = page.total ?? total
    items.push(...pageItems)
    offset += pageItems.length

    if (!pageItems.length || offset >= total) break
  }

  return items
}

export default function DetailedReport() {
  const location = useLocation()
  const navigate = useNavigate()
  const [reportResult, setReportResult] = useState(location?.state?.result ?? null)
  const [samplesLoading, setSamplesLoading] = useState(false)
  const [samplesFetchedForRunId, setSamplesFetchedForRunId] = useState<string | null>(null)
  const reportTitle = location?.state?.reportTitle ?? null
  const [filterUid, setFilterUid] = useState('')
  const [activeSection, setActiveSection] = useState('mismatched')
  const [sectionPage, setSectionPage] = useState(1)
  const [sectionPageSize, setSectionPageSize] = useState(10)
  const [serverPageSamples, setServerPageSamples] = useState<any[]>([])
  const [serverPageLoading, setServerPageLoading] = useState(false)

  useEffect(() => {
    setReportResult(location?.state?.result ?? null)
    setSamplesFetchedForRunId(null)
  }, [location?.state?.result])

  useEffect(() => {
    setSectionPage(1)
  }, [activeSection, filterUid])

  const mismatchCounts = useMemo(() => resolveMismatchCounts(reportResult), [reportResult])
  const totalMismatched = mismatchCounts.value_mismatch
  const totalExtra = mismatchCounts.extra_in_target
  const totalMissing = mismatchCounts.missing_in_target
  const totalAll = Number(
    reportResult?.summary?.total_mismatch_records ?? totalMismatched + totalExtra + totalMissing,
  )

  const sectionTotals = useMemo(
    () => ({
      mismatched: totalMismatched,
      missing_in_target: totalMissing,
      extra_in_target: totalExtra,
    }),
    [totalMismatched, totalMissing, totalExtra],
  )

  useEffect(() => {
    const runId = reportResult?.run_id
    const hasSamples =
      (reportResult?.mismatch_samples?.length ?? 0) > 0 ||
      (reportResult?.mismatch_sample_groups &&
        ((reportResult.mismatch_sample_groups.missing_in_target?.length ?? 0) > 0 ||
          (reportResult.mismatch_sample_groups.extra_in_target?.length ?? 0) > 0 ||
          (reportResult.mismatch_sample_groups.value_mismatch?.length ?? 0) > 0))

    const runIdKey = String(runId)
    if (!runId || hasSamples || samplesLoading || samplesFetchedForRunId === runIdKey) return

    let cancelled = false
    setSamplesLoading(true)

    fetchAllHistoryMismatches(String(runId))
      .then((items) => {
        if (cancelled) return
        setReportResult((current) => {
          if (!current) return current
          return {
            ...current,
            mismatch_samples: items,
            mismatch_sample_groups: buildMismatchSampleGroups(items),
          }
        })
        setSamplesFetchedForRunId(runIdKey)
      })
      .catch(() => {
        setSamplesFetchedForRunId(runIdKey)
      })
      .finally(() => {
        if (!cancelled) setSamplesLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [reportResult, samplesLoading, samplesFetchedForRunId])

  const clientSamples = useMemo(() => {
    const direct = reportResult?.mismatch_samples ?? []
    if (direct.length > 0) return direct
    const groups = reportResult?.mismatch_sample_groups
    if (!groups) return []
    return [
      ...(groups.missing_in_target ?? []),
      ...(groups.extra_in_target ?? []),
      ...(groups.value_mismatch ?? []),
    ]
  }, [reportResult])

  const filteredClientSamples = useMemo(() => {
    if (!filterUid.trim()) return clientSamples
    return clientSamples.filter((sample: any) =>
      sample.uid?.toLowerCase().includes(filterUid.toLowerCase()),
    )
  }, [clientSamples, filterUid])

  const valueMismatch = filteredClientSamples.filter(
    (sample: any) => sample.mismatch_type === 'value_mismatch',
  )
  const extra = filteredClientSamples.filter((sample: any) => sample.mismatch_type === 'extra_in_target')
  const missing = filteredClientSamples.filter(
    (sample: any) => sample.mismatch_type === 'missing_in_target',
  )

  const activeSectionTotal = sectionTotals[activeSection as keyof typeof sectionTotals] ?? 0
  const clientSectionSamples =
    activeSection === 'missing_in_target' ? missing : activeSection === 'extra_in_target' ? extra : valueMismatch
  const useServerPagination =
    Boolean(reportResult?.run_id)
    && !filterUid.trim()
    && activeSectionTotal > clientSectionSamples.length

  useEffect(() => {
    if (!useServerPagination || !reportResult?.run_id) {
      setServerPageSamples([])
      return
    }

    let cancelled = false
    setServerPageLoading(true)
    const mismatchType = sectionMismatchType(activeSection)

    fetchValidationHistoryMismatches(String(reportResult.run_id), {
      limit: sectionPageSize,
      offset: (sectionPage - 1) * sectionPageSize,
      mismatchType,
    })
      .then((page) => {
        if (cancelled) return
        setServerPageSamples((page.items ?? []).map(normalizeMismatchRow))
      })
      .catch(() => {
        if (!cancelled) setServerPageSamples([])
      })
      .finally(() => {
        if (!cancelled) setServerPageLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [useServerPagination, reportResult?.run_id, activeSection, sectionPage, sectionPageSize])

  const activeSamples = useServerPagination ? serverPageSamples : clientSectionSamples
  const reportSectionTotal = filterUid.trim()
    ? clientSectionSamples.length
    : useServerPagination
      ? activeSectionTotal
      : clientSectionSamples.length

  const visibleTotalMismatched = filterUid ? valueMismatch.length : totalMismatched
  const visibleTotalExtra = filterUid ? extra.length : totalExtra
  const visibleTotalMissing = filterUid ? missing.length : totalMissing
  const visibleTotalAll = filterUid
    ? valueMismatch.length + extra.length + missing.length
    : totalAll

  const sections = [
    { key: 'mismatched', label: 'Mismatched', count: visibleTotalMismatched },
    { key: 'missing_in_target', label: 'Missing', count: visibleTotalMissing },
    { key: 'extra_in_target', label: 'Extra', count: visibleTotalExtra },
  ]

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

        {!reportResult ? (
          <Empty description="No report data received. Return to the validation panel and click View Detailed Report." />
        ) : (
          <Space direction="vertical" size={24} style={{ width: '100%' }}>
            <Row gutter={[16, 16]}>
              <Col xs={24} sm={12} lg={6}><Card><Statistic title="Total Wrong Entries" value={visibleTotalAll} /></Card></Col>
              <Col xs={24} sm={12} lg={6}><Card><Statistic title="Mismatched" value={visibleTotalMismatched} valueStyle={{ color: '#d46b08' }} /></Card></Col>
              <Col xs={24} sm={12} lg={6}><Card><Statistic title="Missing in Target" value={visibleTotalMissing} valueStyle={{ color: '#d48806' }} /></Card></Col>
              <Col xs={24} sm={12} lg={6}><Card><Statistic title="Extra in Target" value={visibleTotalExtra} valueStyle={{ color: '#1677ff' }} /></Card></Col>
            </Row>

            <Card title="Filter by UID">
              <Input value={filterUid} onChange={(e) => setFilterUid(e.target.value)} placeholder="Enter UID to search..." />
              {filterUid ? <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>Showing {clientSectionSamples.length} results for UID containing "{filterUid}"</Typography.Paragraph> : null}
            </Card>

            <Segmented
              block
              value={activeSection}
              onChange={(value) => setActiveSection(String(value))}
              options={sections.map((section) => ({ label: `${section.label} (${section.count})`, value: section.key }))}
            />

            <ReportSection
              type={activeSection}
              samples={activeSamples}
              totalCount={reportSectionTotal}
              page={sectionPage}
              pageSize={sectionPageSize}
              loading={serverPageLoading || (samplesLoading && !clientSamples.length)}
              serverPaginated={useServerPagination}
              onPageChange={setSectionPage}
              onPageSizeChange={(nextSize) => {
                setSectionPageSize(nextSize)
                setSectionPage(1)
              }}
            />
          </Space>
        )}
      </div>
    </div>
  )
}
