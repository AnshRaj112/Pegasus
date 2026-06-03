import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Select, DatePicker, Modal, Input, InputNumber, Tag, Table, Button, Card, Col, Row, Progress, Space, Badge } from 'antd'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'
import dayjs from 'dayjs'
import { CheckCircle, XCircle, Activity, Lock, ChevronRight, PlayCircle, Plus } from 'lucide-react'
import {
  createEntityDefinition,
  fetchEntityInsights,
  fetchValidationDailyStats,
  fetchValidationHistory,
  formatDuration
} from '../api/validationHistory'

const { RangePicker } = DatePicker

// Helper: convert ISO/Date to IST (UTC+5:30) and format
function formatToIST(iso: string | undefined, { short = false, compact = false } = {}) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const istMs = d.getTime() + 330 * 60 * 1000 // +5:30
  const ist = new Date(istMs)
  const YYYY = ist.getUTCFullYear()
  const MM = ist.getUTCMonth() // 0-based
  const DD = String(ist.getUTCDate()).padStart(2, '0')
  const hour24 = ist.getUTCHours()
  const hour12 = hour24 % 12 === 0 ? 12 : hour24 % 12
  const mm = String(ist.getUTCMinutes()).padStart(2, '0')
  const suffix = hour24 >= 12 ? 'PM' : 'AM'
  if (short) return compact ? `${hour12} ${suffix}` : `${hour12}:${mm} ${suffix}`
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return `${months[MM]} ${DD}, ${YYYY} ${hour12}:${mm} ${suffix} IST`
}

function getDayBoundaryHourlySeries(runs: any[]) {
  const startOfDay = dayjs().startOf('day')
  const buckets = Array.from({ length: 25 }, (_, index) => {
    const timestamp = startOfDay.add(index, 'hour')
    return {
      date: formatToIST(timestamp.toISOString(), { short: true, compact: true }),
      fullDate: formatToIST(timestamp.toISOString()),
      passed: 0,
      failed: 0,
      total: 0,
    }
  })

  for (const run of runs) {
    const runTime = dayjs(run.completed_at ?? run.created_at)
    if (!runTime.isValid()) continue

    const hourOffset = runTime.startOf('hour').diff(startOfDay, 'hour')
    if (hourOffset < 0 || hourOffset > 24) continue

    const bucket = buckets[hourOffset]
    const passed = run.is_match === true || run.status === 'success'

    if (passed) {
      bucket.passed += 1
    } else {
      bucket.failed += 1
    }
    bucket.total += 1
  }

  return buckets
}

function formatDailyTick(value: string) {
  const match = typeof value === 'string' ? value.match(/^(\d{1,2})(?::00)?\s([AP]M)$/) : null
  if (!match) return value
  const hour = Number.parseInt(match[1], 10)
  const suffix = match[2]
  const displayHour = hour % 12 === 0 ? 12 : hour % 12
  return `${displayHour} ${suffix}`
}

function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: '#ffffff',
        border: '1px solid #d1d5db',
        borderRadius: 8,
        padding: '12px',
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
      }}>
        <p style={{ fontWeight: 600, color: '#111827', marginBottom: 8 }}>{payload[0]?.payload?.fullDate ?? label}</p>
        {payload.map((entry: any, index: number) => (
          <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: entry.color }} />
            <span style={{ color: '#6b7280' }}>{entry.name}:</span>
            <span style={{ fontWeight: 600, color: '#111827' }}>{entry.value}</span>
          </div>
        ))}
      </div>
    )
  }
  return null
}

function bucketRunStatus(detail: any) {
  const status = String(detail?.status || '').toLowerCase()
  const isPassed = detail?.is_match === true && status === 'completed'
  if (isPassed) return 'passed'
  if (status === 'running') return 'running'
  if (status === 'pending' || status === 'queued' || status === 'scheduled') return 'scheduled'
  if (status === 'completed' || status === 'failed') return 'failed'
  return 'failed'
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [filterType, setFilterType] = useState('weekly')
  const [dateRange, setDateRange] = useState<any>(null)
  const [chartData, setChartData] = useState<any[]>([])
  const [totals, setTotals] = useState({ passed: 0, failed: 0, total: 0 })
  const [entityInsights, setEntityInsights] = useState<any[]>([])
  const [entityLimit, setEntityLimit] = useState(25)
  const [entityError, setEntityError] = useState('')
  const [createEntityModal, setCreateEntityModal] = useState({ open: false, candidate: null, displayName: '', aliases: '' })
  const [savingEntity, setSavingEntity] = useState(false)

  // Active running tasks
  const [activeTasks, setActiveTasks] = useState([
    { key: '1', task_name: 'Core_Validation_Payroll_GCS_Run_224', status: 'running', progress: 78 },
    { key: '2', task_name: 'Employee_Header_Sanitization_Job', status: 'running', progress: 42 },
    { key: '3', task_name: 'Quarterly_Tax_File_Check_Manual', status: 'scheduled', progress: 0 },
  ])

  // Workspaces list
  const [workspaces, setWorkspaces] = useState([
    { key: '1', name: 'Global Workspace', status: 'System Default', pinned: true },
    { key: '2', name: 'Payroll & HR Division', status: 'Active', pinned: false },
    { key: '3', name: 'Compliance Audits 2026', status: 'Active', pinned: false },
  ])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (filterType === 'custom' && (!dateRange?.[0] || !dateRange?.[1])) {
        if (!cancelled) {
          setChartData([])
          setTotals({ passed: 0, failed: 0, total: 0 })
        }
        return
      }
      try {
        if (filterType === 'daily') {
          const data = await fetchValidationHistory({ limit: 200, offset: 0 })
          if (cancelled) return
          const items = Array.isArray(data.items) ? data.items : []
          const todayStart = dayjs().startOf('day')
          const todayEnd = todayStart.add(1, 'day')
          const dailyRuns = items.filter((row: any) => {
            const completedAt = dayjs(row.completed_at ?? row.created_at)
            return completedAt.isValid() && completedAt.isAfter(todayStart.subtract(1, 'millisecond')) && completedAt.isBefore(todayEnd.add(1, 'millisecond'))
          })

          const hourlySeries = getDayBoundaryHourlySeries(dailyRuns)
          setChartData(hourlySeries)
          setTotals({
            passed: hourlySeries.reduce((sum, row) => sum + row.passed, 0),
            failed: hourlySeries.reduce((sum, row) => sum + row.failed, 0),
            total: hourlySeries.reduce((sum, row) => sum + row.total, 0),
          })
          return
        }

        const opts =
          filterType === 'custom'
            ? { from: dateRange[0].format('YYYY-MM-DD'), to: dateRange[1].format('YYYY-MM-DD') }
            : {
                days:
                  filterType === 'weekly' ? 7 : filterType === 'monthly' ? 30 : 1,
              }

        const data = await fetchValidationDailyStats(opts)
        if (cancelled) return
        const items = data.items ?? []
        const isHourly = filterType === 'daily'
        setChartData(
          items.map((row: any) => ({
            date: isHourly ? formatToIST(row.date, { short: true }) : dayjs(row.date).format('MMM DD'),
            fullDate: isHourly ? formatToIST(row.date) : dayjs(row.date).format('MMM DD, YYYY'),
            passed: row.passed,
            failed: row.failed,
            total: row.total,
          }))
        )
        const t = data.totals ?? { passed: 0, failed: 0, total: 0 }
        setTotals({
          passed: t.passed ?? 0,
          failed: t.failed ?? 0,
          total: t.total ?? (t.passed ?? 0) + (t.failed ?? 0),
        })
      } catch {
        if (!cancelled) {
          setChartData([])
          setTotals({ passed: 0, failed: 0, total: 0 })
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [filterType, dateRange])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await fetchEntityInsights({ limit: entityLimit })
        if (cancelled) return
        setEntityInsights(Array.isArray(data.entities) ? data.entities : [])
        setEntityError('')
      } catch (error) {
        if (!cancelled) {
          setEntityInsights([])
          setEntityError(error instanceof Error ? error.message : 'Failed to load entity insights')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [entityLimit])

  async function handleCreateEntity() {
    if (!createEntityModal.displayName.trim()) return
    setSavingEntity(true)
    try {
      const aliases = createEntityModal.aliases
        .split(',')
        .map((item: string) => item.trim())
        .filter(Boolean)
      await createEntityDefinition({
        displayName: createEntityModal.displayName.trim(),
        aliases,
      })
      setCreateEntityModal({ open: false, candidate: null, displayName: '', aliases: '' })
      const refreshed = await fetchEntityInsights({ limit: entityLimit })
      setEntityInsights(Array.isArray(refreshed.entities) ? refreshed.entities : [])
      setEntityError('')
    } catch (error) {
      setEntityError(error instanceof Error ? error.message : 'Failed to create entity')
    } finally {
      setSavingEntity(false)
    }
  }

  const entityTableData = entityInsights.map((entity: any) => {
    const details = Array.isArray(entity.details) ? entity.details : []
    const bucketCounts = details.reduce(
      (acc: any, detail: any) => {
        const bucket = bucketRunStatus(detail)
        acc[bucket] += 1
        return acc
      },
      { passed: 0, failed: 0, running: 0, scheduled: 0 }
    )
    return {
      ...entity,
      key: entity.inferred_entity,
      statusCounts: bucketCounts,
    }
  })

  const entityStats = entityTableData.reduce((acc, row) => {
    acc.entities += 1
    acc.validations += Number(row.total_count || 0)
    if (row.matched_existing_entity) acc.known += 1
    else acc.needsConfirmation += 1
    return acc
  }, {
    entities: 0,
    validations: 0,
    known: 0,
    needsConfirmation: 0,
  })

  const entityColumns = [
    {
      title: 'Entity display pattern name',
      dataIndex: 'display_name',
      key: 'display_name',
      render: (_: any, row: any) => (
        <Space direction="vertical" size={2} style={{ width: '100%' }}>
          <Space>
            <a 
              onClick={(e) => {
                e.stopPropagation()
                navigate(`/dashboard/${row.inferred_entity || row.display_name}`)
              }}
              style={{ fontWeight: 600, color: '#1677ff', cursor: 'pointer' }}
            >
              {row.display_name}
            </a>
            <Tag color={row.matched_existing_entity ? 'green' : 'orange'}>
              {row.matched_existing_entity ? 'Known' : 'Needs review'}
            </Tag>
          </Space>
          <span style={{ color: '#9ca3af', fontSize: '12px' }}>
            {row.confidence ? `Confidence ${row.confidence}` : 'No confidence score'}
          </span>
        </Space>
      ),
    },
    {
      title: 'Passed',
      dataIndex: ['statusCounts', 'passed'],
      key: 'passed',
      width: 90,
      align: 'center' as const,
      render: (value: number) => (
        <span style={{ display: 'inline-flex', minWidth: 34, justifyContent: 'center', padding: '2px 8px', borderRadius: 999, background: 'rgba(34,197,94,0.10)', color: '#22c55e', fontWeight: 700 }}>
          {value}
        </span>
      ),
    },
    {
      title: 'Failed',
      dataIndex: ['statusCounts', 'failed'],
      key: 'failed',
      width: 90,
      align: 'center' as const,
      render: (value: number) => (
        <span style={{ display: 'inline-flex', minWidth: 34, justifyContent: 'center', padding: '2px 8px', borderRadius: 999, background: 'rgba(239,68,68,0.10)', color: '#ef4444', fontWeight: 700 }}>
          {value}
        </span>
      ),
    },
    {
      title: 'Running',
      dataIndex: ['statusCounts', 'running'],
      key: 'running',
      width: 90,
      align: 'center' as const,
      render: (value: number) => (
        <span style={{ display: 'inline-flex', minWidth: 34, justifyContent: 'center', padding: '2px 8px', borderRadius: 999, background: 'rgba(59,130,246,0.10)', color: '#3b82f6', fontWeight: 700 }}>
          {value}
        </span>
      ),
    },
    {
      title: 'Total',
      dataIndex: 'total_count',
      key: 'total_count',
      width: 90,
      align: 'center' as const,
      render: (value: number) => (
        <span style={{ display: 'inline-flex', minWidth: 34, justifyContent: 'center', padding: '2px 8px', borderRadius: 999, background: '#f3f4f6', color: '#111827', fontWeight: 700 }}>
          {value}
        </span>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      width: 150,
      align: 'center' as const,
      render: (_: any, row: any) =>
        row.matched_existing_entity ? (
          <span style={{ color: '#9ca3af', fontSize: 12 }}>Reviewed</span>
        ) : (
          <Button
            size="small"
            type="primary"
            onClick={(e) => {
              e.stopPropagation()
              setCreateEntityModal({
                open: true,
                candidate: row,
                displayName: row.display_name,
                aliases: (row.candidate_tokens || []).join(','),
              })
            }}
          >
            Create Entity
          </Button>
        ),
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Title block */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#111827', margin: 0, letterSpacing: '-0.02em' }}>
            Validation Dashboard
          </h1>
          <p style={{ color: '#6b7280', margin: '4px 0 0 0' }}>
            System-wide activity overview, active workspace trackers, and entity mappings.
          </p>
        </div>

        {/* Date Filters */}
        <Space>
          <Select
            value={filterType}
            onChange={(val) => {
              setFilterType(val)
              if (val !== 'custom') setDateRange(null)
            }}
            style={{ width: 140 }}
            options={[
              { value: 'daily', label: 'Last 1 Day' },
              { value: 'weekly', label: 'Last 7 Days' },
              { value: 'monthly', label: 'Last 30 Days' },
              { value: 'custom', label: 'Custom Range' },
            ]}
          />
          {filterType === 'custom' && (
            <RangePicker
              value={dateRange}
              onChange={setDateRange}
              style={{ width: 260 }}
            />
          )}
        </Space>
      </div>

      {/* Metrics Row */}
      <Row gutter={16}>
        <Col span={8}>
          <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <Space align="center" size={16}>
              <div style={{ padding: '12px', borderRadius: '12px', background: 'rgba(59,130,246,0.1)', color: '#3b82f6' }}>
                <Activity size={24} />
              </div>
              <div>
                <span style={{ color: '#6b7280', fontSize: '13px', fontWeight: 500 }}>Total Validations</span>
                <h2 style={{ margin: 0, fontSize: '28px', fontWeight: 700, color: '#111827', lineHeight: 1.2 }}>
                  {totals.total.toLocaleString()}
                </h2>
              </div>
            </Space>
          </Card>
        </Col>
        <Col span={8}>
          <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <Space align="center" size={16}>
              <div style={{ padding: '12px', borderRadius: '12px', background: 'rgba(34,197,94,0.1)', color: '#22c55e' }}>
                <CheckCircle size={24} />
              </div>
              <div>
                <span style={{ color: '#6b7280', fontSize: '13px', fontWeight: 500 }}>Total Passed</span>
                <h2 style={{ margin: 0, fontSize: '28px', fontWeight: 700, color: '#111827', lineHeight: 1.2 }}>
                  {totals.passed.toLocaleString()}
                </h2>
                <span style={{ color: '#22c55e', fontSize: '12px', fontWeight: 600 }}>
                  {totals.total ? ((totals.passed / totals.total) * 100).toFixed(1) : '0.0'}% success rate
                </span>
              </div>
            </Space>
          </Card>
        </Col>
        <Col span={8}>
          <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <Space align="center" size={16}>
              <div style={{ padding: '12px', borderRadius: '12px', background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}>
                <XCircle size={24} />
              </div>
              <div>
                <span style={{ color: '#6b7280', fontSize: '13px', fontWeight: 500 }}>Total Failed</span>
                <h2 style={{ margin: 0, fontSize: '28px', fontWeight: 700, color: '#111827', lineHeight: 1.2 }}>
                  {totals.failed.toLocaleString()}
                </h2>
                <span style={{ color: '#ef4444', fontSize: '12px', fontWeight: 600 }}>
                  {totals.total ? ((totals.failed / totals.total) * 100).toFixed(1) : '0.0'}% failure rate
                </span>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* Main Charts & Sidebars */}
      <Row gutter={16}>
        {/* Validation Trends Area Chart */}
        <Col span={16}>
          <Card title="Validation Trends" bordered={false} style={{ height: '420px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <div style={{ height: '320px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorPassed" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorFailed" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: '#9ca3af', fontSize: 11 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#9ca3af', fontSize: 11 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" />
                  <Area type="monotone" dataKey="passed" name="Passed" stroke="#22c55e" strokeWidth={2} fillOpacity={1} fill="url(#colorPassed)" />
                  <Area type="monotone" dataKey="failed" name="Failed" stroke="#ef4444" strokeWidth={2} fillOpacity={1} fill="url(#colorFailed)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Col>

        {/* Right Sidebar: Pinned Workspaces & Tasks */}
        <Col span={8}>
          <Card title="Active Running Tasks" bordered={false} style={{ height: '420px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {activeTasks.map(task => (
                <div key={task.key} style={{ borderBottom: '1px solid #f3f4f6', paddingBottom: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 600, fontSize: '13px', color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }}>
                      {task.task_name}
                    </span>
                    <Badge
                      status={task.status === 'running' ? 'processing' : 'default'}
                      text={task.status.toUpperCase()}
                      style={{ fontSize: '11px', fontWeight: 600 }}
                    />
                  </div>
                  <Progress percent={task.progress} size="small" status={task.status === 'running' ? 'active' : 'normal'} />
                </div>
              ))}

              <div style={{ marginTop: 'auto', paddingTop: '10px' }}>
                <h4 style={{ fontSize: '12px', fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Workspace Pinned Lists
                </h4>
                {workspaces.map(ws => (
                  <div key={ws.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px', borderRadius: '6px', background: '#f9fafb', marginBottom: '6px' }}>
                    <Space size={6}>
                      {ws.pinned && <Lock size={12} color="#9ca3af" />}
                      <span style={{ fontSize: '13px', fontWeight: 500, color: '#111827' }}>{ws.name}</span>
                    </Space>
                    <Tag color={ws.pinned ? 'blue' : 'default'}>{ws.status}</Tag>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* Entity Table Customizer */}
      <Card bordered={false} style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#111827', margin: 0 }}>
              How reliably filenames map to entities
            </h3>
            <p style={{ margin: '4px 0 0 0', color: '#6b7280', fontSize: '13px' }}>
              Entity is inferred from source and target file names. Click display name to inspect.
            </p>
          </div>
          <Space>
            <span style={{ fontSize: '13px', color: '#4b5563' }}>Limit:</span>
            <InputNumber min={5} max={500} value={entityLimit} onChange={(v) => setEntityLimit(Number(v) || 25)} style={{ width: '80px' }} />
            <span style={{ fontSize: '13px', color: '#4b5563' }}>files</span>
          </Space>
        </div>

        {/* Entity Stats Summary */}
        <Row gutter={10} style={{ marginBottom: '16px' }}>
          <Col span={6}>
            <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '10px 14px' }}>
              <div style={{ fontSize: '10px', fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase' }}>Entities</div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#111827' }}>{entityStats.entities}</div>
            </div>
          </Col>
          <Col span={6}>
            <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '10px 14px' }}>
              <div style={{ fontSize: '10px', fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase' }}>Validations</div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#111827' }}>{entityStats.validations}</div>
            </div>
          </Col>
          <Col span={6}>
            <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '10px 14px' }}>
              <div style={{ fontSize: '10px', fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase' }}>Known</div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#22c55e' }}>{entityStats.known}</div>
            </div>
          </Col>
          <Col span={6}>
            <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '10px 14px' }}>
              <div style={{ fontSize: '10px', fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase' }}>Needs Review</div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#faad14' }}>{entityStats.needsConfirmation}</div>
            </div>
          </Col>
        </Row>

        <Table
          columns={entityColumns}
          dataSource={entityTableData}
          pagination={false}
          size="middle"
          scroll={{ x: 800 }}
          locale={{ emptyText: entityError ? '—' : 'No recent validation history found for entity inference.' }}
          onRow={(record) => ({
            onClick: () => {
              navigate(`/dashboard/${record.inferred_entity || record.display_name}`)
            },
            style: { cursor: 'pointer' }
          })}
          expandable={{
            expandedRowRender: (entityRow: any) => (
              <Table
                size="small"
                pagination={false}
                rowKey={(detail) => detail.run_id}
                dataSource={(entityRow.details || []).map((detail: any) => ({
                  ...detail,
                  status_bucket: bucketRunStatus(detail),
                }))}
                columns={[
                  {
                    title: 'Source File',
                    dataIndex: 'source_filename',
                    key: 'source_filename',
                    render: (val) => val || '—',
                  },
                  {
                    title: 'Target File',
                    dataIndex: 'target_filename',
                    key: 'target_filename',
                    render: (val) => val || '—',
                  },
                  {
                    title: 'Status',
                    dataIndex: 'status_bucket',
                    key: 'status_bucket',
                    render: (val: string) => {
                      const colorMap: Record<string, string> = {
                        passed: 'green',
                        failed: 'red',
                        running: 'blue',
                        scheduled: 'gold',
                      }
                      return <Tag color={colorMap[val] || 'default'}>{String(val).toUpperCase()}</Tag>
                    },
                  },
                  {
                    title: 'Completed At',
                    dataIndex: 'completed_at',
                    key: 'completed_at',
                    render: (val) => formatToIST(val) || '—',
                  },
                ]}
              />
            ),
            rowExpandable: (record) => Array.isArray(record.details) && record.details.length > 0,
            onExpand: (expanded, record) => {
              // stop row click propagation on expand toggle
            }
          }}
        />
      </Card>

      {/* Create Entity Modal */}
      <Modal
        open={createEntityModal.open}
        title="Create Entity from Filename Pattern"
        onCancel={() => setCreateEntityModal({ open: false, candidate: null, displayName: '', aliases: '' })}
        onOk={handleCreateEntity}
        okText="Create Entity"
        confirmLoading={savingEntity}
      >
        <div style={{ display: 'grid', gap: '14px', marginTop: '14px' }}>
          <div>
            <p style={{ marginBottom: 6, color: '#4b5563', fontSize: 13, fontWeight: 500 }}>Entity display name</p>
            <Input
              value={createEntityModal.displayName}
              onChange={(e) => setCreateEntityModal((prev) => ({ ...prev, displayName: e.target.value }))}
              placeholder="Employee"
            />
          </div>
          <div>
            <p style={{ marginBottom: 6, color: '#4b5563', fontSize: 13, fontWeight: 500 }}>Aliases (comma-separated)</p>
            <Input
              value={createEntityModal.aliases}
              onChange={(e) => setCreateEntityModal((prev) => ({ ...prev, aliases: e.target.value }))}
              placeholder="employee,emp,staff"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
