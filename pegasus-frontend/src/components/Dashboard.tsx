import { useEffect, useState } from 'react'
import { Select, DatePicker, Modal, Input, InputNumber, Tag, Table, Button } from 'antd'
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
// Helper: convert ISO/Date to IST (UTC+5:30) and format
function formatToIST(iso, { short = false, compact = false } = {}) {
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
import { CheckCircle, XCircle, Activity } from 'lucide-react'
import ActiveValidationsPanel from './ActiveValidationsPanel'
import {
  createEntityDefinition,
  fetchEntityInsights,
  fetchValidationDailyStats,
  fetchValidationHistory,
} from '../api/validationHistory'

const { RangePicker } = DatePicker

function getDayBoundaryHourlySeries(runs) {
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

function formatDailyTick(value) {
  const match = typeof value === 'string' ? value.match(/^(\d{1,2})(?::00)?\s([AP]M)$/) : null
  if (!match) return value
  const hour = Number.parseInt(match[1], 10)
  const suffix = match[2]
  const displayHour = hour % 12 === 0 ? 12 : hour % 12
  return `${displayHour} ${suffix}`
}

function CustomTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: 'var(--surface-0)',
        border: '1px solid var(--border-2)',
        borderRadius: 8,
        padding: '12px',
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
      }}>
        <p style={{ fontWeight: 600, color: 'var(--text-1)', marginBottom: 8 }}>{payload[0]?.payload?.fullDate ?? label}</p>
        {payload.map((entry, index) => (
          <div key={index} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: entry.color }} />
            <span style={{ color: 'var(--text-2)' }}>{entry.name}:</span>
            <span style={{ fontWeight: 600, color: 'var(--text-1)' }}>{entry.value}</span>
          </div>
        ))}
      </div>
    )
  }
  return null
}

function bucketRunStatus(detail) {
  const status = String(detail?.status || '').toLowerCase()
  const isPassed = detail?.is_match === true && status === 'completed'
  if (isPassed) return 'passed'
  if (status === 'running') return 'running'
  if (status === 'pending' || status === 'queued' || status === 'scheduled') return 'scheduled'
  if (status === 'completed' || status === 'failed') return 'failed'
  return 'failed'
}

export default function Dashboard() {
  const [filterType, setFilterType] = useState('weekly')
  const [dateRange, setDateRange] = useState(null)
  const [chartData, setChartData] = useState([])
  const [totals, setTotals] = useState({ passed: 0, failed: 0, total: 0 })
  const [entityInsights, setEntityInsights] = useState([])
  const [entityLimit, setEntityLimit] = useState(25)
  const [entityError, setEntityError] = useState('')
  const [createEntityModal, setCreateEntityModal] = useState({ open: false, candidate: null, displayName: '', aliases: '' })
  const [savingEntity, setSavingEntity] = useState(false)

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
          const dailyRuns = items.filter((row) => {
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
          items.map((row) => ({
            // For 1-day view show hourly labels in IST; otherwise show month/day
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
        .map((item) => item.trim())
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

  const entityTableData = entityInsights.map((entity) => {
    const details = Array.isArray(entity.details) ? entity.details : []
    const bucketCounts = details.reduce(
      (acc, detail) => {
        const bucket = bucketRunStatus(detail)
        acc[bucket] += 1
        return acc
      },
      { passed: 0, failed: 0, running: 0, scheduled: 0 },
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
      title: 'Entity',
      dataIndex: 'display_name',
      key: 'display_name',
      render: (_, row) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{row.display_name}</span>
            <Tag color={row.matched_existing_entity ? 'green' : 'orange'} style={{ marginInlineEnd: 0 }}>
              {row.matched_existing_entity ? 'Known' : 'Needs review'}
            </Tag>
          </div>
          <div style={{ color: 'var(--text-3)', fontSize: 12, lineHeight: 1.35 }}>
            {row.confidence ? `Confidence ${row.confidence}` : 'No confidence score'}
          </div>
        </div>
      ),
    },
    {
      title: 'Passed',
      dataIndex: ['statusCounts', 'passed'],
      key: 'passed',
      width: 90,
      align: 'center',
      render: (value) => (
        <span style={{ display: 'inline-flex', minWidth: 34, justifyContent: 'center', padding: '4px 8px', borderRadius: 999, background: 'rgba(34,197,94,0.10)', color: 'var(--success)', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </span>
      ),
    },
    {
      title: 'Failed',
      dataIndex: ['statusCounts', 'failed'],
      key: 'failed',
      width: 90,
      align: 'center',
      render: (value) => (
        <span style={{ display: 'inline-flex', minWidth: 34, justifyContent: 'center', padding: '4px 8px', borderRadius: 999, background: 'rgba(239,68,68,0.10)', color: 'var(--danger)', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </span>
      ),
    },
    {
      title: 'Running',
      dataIndex: ['statusCounts', 'running'],
      key: 'running',
      width: 90,
      align: 'center',
      render: (value) => (
        <span style={{ display: 'inline-flex', minWidth: 34, justifyContent: 'center', padding: '4px 8px', borderRadius: 999, background: 'rgba(59,130,246,0.10)', color: 'var(--blue, #3b82f6)', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </span>
      ),
    },
    {
      title: 'Scheduled',
      dataIndex: ['statusCounts', 'scheduled'],
      key: 'scheduled',
      width: 110,
      align: 'center',
      render: (value) => (
        <span style={{ display: 'inline-flex', minWidth: 34, justifyContent: 'center', padding: '4px 8px', borderRadius: 999, background: 'rgba(245,158,11,0.12)', color: 'var(--warning, #d97706)', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </span>
      ),
    },
    {
      title: 'Total',
      dataIndex: 'total_count',
      key: 'total_count',
      width: 90,
      align: 'center',
      render: (value) => (
        <span style={{ display: 'inline-flex', minWidth: 34, justifyContent: 'center', padding: '4px 8px', borderRadius: 999, background: 'var(--surface-2)', color: 'var(--text-1)', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </span>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      width: 150,
      align: 'center',
      render: (_, row) =>
        row.matched_existing_entity ? (
          <span style={{ color: 'var(--text-3)', fontSize: 12 }}>Reviewed</span>
        ) : (
          <Button
            size="small"
            type="primary"
            onClick={() =>
              setCreateEntityModal({
                open: true,
                candidate: row,
                displayName: row.display_name,
                aliases: (row.candidate_tokens || []).join(','),
              })
            }
          >
            Create Entity
          </Button>
        ),
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, animation: 'fade-in 0.3s ease-out' }}>
      {/* Header and Filter */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.02em', margin: 0 }}>
            Validation Dashboard
          </h1>
          <p style={{ color: 'var(--text-2)', margin: '4px 0 0 0' }}>
            Monitor live validations, resource footprint, and historical success rates.
          </p>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Select
            value={filterType}
            onChange={(val) => {
              setFilterType(val)
              if (val !== 'custom') setDateRange(null)
            }}
            style={{ width: 120 }}
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
        </div>
      </div>

      <ActiveValidationsPanel showResourceDetails />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24, alignItems: 'start' }}>
        {/* Main Chart Area */}
        <div className="card" style={{ padding: 24, height: 540, display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-1)', margin: 0, paddingBottom: 18 }}>
            Validation Trends
          </h3>
          <div style={{ flex: 1, minHeight: 0, paddingTop: 12 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 28, left: 0, bottom: 46 }}>
                <defs>
                  <linearGradient id="colorPassed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--success)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--success)" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorFailed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--danger)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--danger)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-1)" />
                <XAxis 
                  dataKey="date" 
                  axisLine={false} 
                  tickLine={false} 
                  height={56}
                  tick={{ fill: 'var(--text-3)', fontSize: filterType === 'daily' ? 11 : 12 }}
                  padding={filterType === 'daily' ? { left: 12, right: 24 } : { left: 0, right: 0 }}
                  interval={filterType === 'daily' ? 2 : 'preserveStartEnd'}
                  minTickGap={filterType === 'daily' ? 24 : 30}
                  angle={filterType === 'daily' ? 0 : 0}
                  textAnchor="middle"
                  tickMargin={filterType === 'daily' ? 24 : 10}
                  dy={filterType === 'daily' ? 12 : 10}
                  tickFormatter={filterType === 'daily' ? formatDailyTick : undefined}
                />
                <YAxis 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: 'var(--text-3)', fontSize: 12 }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  iconType="circle"
                  wrapperStyle={{ paddingTop: 28 }}
                  wrapperClassName="dashboard-legend"
                  content={({ payload }) => (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 24, width: '100%', paddingTop: 12, paddingBottom: 4 }}>
                      {(payload ?? []).map((entry) => (
                        <div key={entry.value} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ width: 10, height: 10, borderRadius: 9999, background: entry.color, display: 'inline-block' }} />
                          <span style={{ color: 'var(--text-2)', fontSize: 13, fontWeight: 500 }}>{entry.value}</span>
                        </div>
                      ))}
                    </div>
                  )}
                />
                <Area 
                  type="monotone" 
                  dataKey="passed" 
                  name="Passed"
                  stroke="var(--success)" 
                  strokeWidth={2}
                  fillOpacity={1} 
                  fill="url(#colorPassed)" 
                />
                <Area 
                  type="monotone" 
                  dataKey="failed" 
                  name="Failed"
                  stroke="var(--danger)" 
                  strokeWidth={2}
                  fillOpacity={1} 
                  fill="url(#colorFailed)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Statistics Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card" style={{ padding: 20, display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ 
              width: 48, height: 48, borderRadius: 12, 
              background: 'var(--blue-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--blue)'
            }}>
              <Activity size={24} />
            </div>
            <div>
              <p style={{ margin: 0, color: 'var(--text-2)', fontSize: 13, fontWeight: 500 }}>Total Validations</p>
              <h2 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: 'var(--text-1)', lineHeight: 1.2 }}>
                {totals.total.toLocaleString()}
              </h2>
            </div>
          </div>

          <div className="card" style={{ padding: 20, display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ 
              width: 48, height: 48, borderRadius: 12, 
              background: 'var(--success-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--success)'
            }}>
              <CheckCircle size={24} />
            </div>
            <div>
              <p style={{ margin: 0, color: 'var(--text-2)', fontSize: 13, fontWeight: 500 }}>Total Passed</p>
              <h2 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: 'var(--text-1)', lineHeight: 1.2 }}>
                {totals.passed.toLocaleString()}
              </h2>
              <p style={{ margin: '4px 0 0 0', color: 'var(--success)', fontSize: 12, fontWeight: 500 }}>
                {totals.total ? ((totals.passed / totals.total) * 100).toFixed(1) : '0.0'}% success rate
              </p>
            </div>
          </div>

          <div className="card" style={{ padding: 20, display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ 
              width: 48, height: 48, borderRadius: 12, 
              background: 'var(--danger-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--danger)'
            }}>
              <XCircle size={24} />
            </div>
            <div>
              <p style={{ margin: 0, color: 'var(--text-2)', fontSize: 13, fontWeight: 500 }}>Total Failed</p>
              <h2 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: 'var(--text-1)', lineHeight: 1.2 }}>
                {totals.failed.toLocaleString()}
              </h2>
              <p style={{ margin: '4px 0 0 0', color: 'var(--danger)', fontSize: 12, fontWeight: 500 }}>
                {totals.total ? ((totals.failed / totals.total) * 100).toFixed(1) : '0.0'}% failure rate
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{
        padding: 24,
        border: '1px solid var(--border-1)',
        background: 'linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(248,250,252,0.92) 100%)',
        boxShadow: '0 10px 32px rgba(15,23,42,0.05)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', marginBottom: 18, flexWrap: 'wrap' }}>
          <div style={{ minWidth: 260, flex: '1 1 360px' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderRadius: 999, background: 'var(--surface-2)', border: '1px solid var(--border-1)', color: 'var(--text-2)', fontSize: 12, fontWeight: 600, marginBottom: 10 }}>
              Entity Health
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)' }} />
              <span>Last {entityLimit} validations</span>
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-1)', margin: 0, letterSpacing: '-0.02em' }}>How reliably filenames map to entities</h3>
            <p style={{ margin: '8px 0 0 0', color: 'var(--text-2)', fontSize: 13, lineHeight: 1.5, maxWidth: 720 }}>
              Entity is inferred from source and target file names such as <code>employee_ddmmyy_timestamp</code>. Use the limit to widen or narrow the history window.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border-1)' }}>
              <span style={{ color: 'var(--text-2)', fontSize: 13 }}>Last</span>
              <InputNumber min={5} max={500} value={entityLimit} onChange={(v) => setEntityLimit(Number(v) || 25)} />
              <span style={{ color: 'var(--text-2)', fontSize: 13 }}>files</span>
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10, marginBottom: 16 }}>
          <div style={{ padding: '12px 14px', borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border-1)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>Entities</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', lineHeight: 1 }}>{entityStats.entities}</div>
          </div>
          <div style={{ padding: '12px 14px', borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border-1)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>Validations</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', lineHeight: 1 }}>{entityStats.validations.toLocaleString()}</div>
          </div>
          <div style={{ padding: '12px 14px', borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border-1)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>Known</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--success)', lineHeight: 1 }}>{entityStats.known}</div>
          </div>
          <div style={{ padding: '12px 14px', borderRadius: 14, background: 'var(--surface-2)', border: '1px solid var(--border-1)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-4)', marginBottom: 6 }}>Needs review</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--warning, #d97706)', lineHeight: 1 }}>{entityStats.needsConfirmation}</div>
          </div>
        </div>

        {entityError && (
          <div style={{ marginBottom: 12, color: 'var(--danger)', fontSize: 13 }}>{entityError}</div>
        )}

        <div style={{ borderRadius: 16, overflow: 'hidden', border: '1px solid var(--border-1)', background: 'var(--surface-0)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, padding: '12px 16px', borderBottom: '1px solid var(--border-1)', background: 'rgba(248,250,252,0.9)' }}>
            <div style={{ color: 'var(--text-2)', fontSize: 12 }}>
              Showing {entityTableData.length} entity pattern{entityTableData.length === 1 ? '' : 's'}
            </div>
            <div style={{ color: 'var(--text-3)', fontSize: 12 }}>
              Click a row to inspect validation details.
            </div>
          </div>
          <Table
            columns={entityColumns}
            dataSource={entityTableData}
            pagination={false}
            size="middle"
            bordered={false}
            tableLayout="fixed"
            scroll={{ x: 920 }}
            locale={{ emptyText: entityError ? '—' : 'No recent validation history found for entity inference.' }}
            expandable={{
            expandedRowRender: (entityRow) => (
              <Table
                size="small"
                pagination={false}
                rowKey={(detail) => detail.run_id}
                dataSource={(entityRow.details || []).map((detail) => ({
                  ...detail,
                  status_bucket: bucketRunStatus(detail),
                }))}
                columns={[
                  {
                    title: 'Source File',
                    dataIndex: 'source_filename',
                    key: 'source_filename',
                    render: (value) => value || '—',
                  },
                  {
                    title: 'Target File',
                    dataIndex: 'target_filename',
                    key: 'target_filename',
                    render: (value) => value || '—',
                  },
                  {
                    title: 'Status',
                    dataIndex: 'status_bucket',
                    key: 'status_bucket',
                    render: (value) => {
                      const colorMap = {
                        passed: 'green',
                        failed: 'red',
                        running: 'blue',
                        scheduled: 'gold',
                      }
                      return <Tag color={colorMap[value] || 'default'}>{String(value).toUpperCase()}</Tag>
                    },
                  },
                  {
                    title: 'Completed At',
                    dataIndex: 'completed_at',
                    key: 'completed_at',
                    render: (value) => formatToIST(value) || '—',
                  },
                ]}
              />
            ),
              rowExpandable: (record) => Array.isArray(record.details) && record.details.length > 0,
            }}
          />
        </div>
      </div>

      <Modal
        open={createEntityModal.open}
        title="Create Entity from Filename Pattern"
        onCancel={() => setCreateEntityModal({ open: false, candidate: null, displayName: '', aliases: '' })}
        onOk={handleCreateEntity}
        okText="Create Entity"
        confirmLoading={savingEntity}
      >
        <div style={{ display: 'grid', gap: 10 }}>
          <div>
            <p style={{ marginBottom: 6, color: 'var(--text-2)', fontSize: 13 }}>Entity display name</p>
            <Input
              value={createEntityModal.displayName}
              onChange={(e) => setCreateEntityModal((prev) => ({ ...prev, displayName: e.target.value }))}
              placeholder="Employee"
            />
          </div>
          <div>
            <p style={{ marginBottom: 6, color: 'var(--text-2)', fontSize: 13 }}>Aliases (comma-separated)</p>
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
