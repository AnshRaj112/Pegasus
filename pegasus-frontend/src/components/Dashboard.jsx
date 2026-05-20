import React, { useEffect, useState } from 'react'
import { Select, DatePicker } from 'antd'
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
import { CheckCircle, XCircle, Activity } from 'lucide-react'
import { fetchValidationDailyStats, fetchValidationHistory } from '../api/validationHistory'

const { RangePicker } = DatePicker

function getDayBoundaryHourlySeries(runs) {
  const startOfDay = dayjs().startOf('day')
  const buckets = Array.from({ length: 25 }, (_, index) => {
    const timestamp = startOfDay.add(index, 'hour')
    return {
      date: timestamp.format('h:mm A'),
      fullDate: timestamp.toISOString(),
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

export default function Dashboard() {
  const [filterType, setFilterType] = useState('weekly')
  const [dateRange, setDateRange] = useState(null)
  const [chartData, setChartData] = useState([])
  const [totals, setTotals] = useState({ passed: 0, failed: 0, total: 0 })

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
        setChartData(
          items.map((row) => ({
            date: dayjs(row.date).format('MMM DD'),
            fullDate: row.date,
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

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          background: 'var(--surface-0)',
          border: '1px solid var(--border-2)',
          borderRadius: 8,
          padding: '12px',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
        }}>
          <p style={{ fontWeight: 600, color: 'var(--text-1)', marginBottom: 8 }}>{label}</p>
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, animation: 'fade-in 0.3s ease-out' }}>
      {/* Header and Filter */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.02em', margin: 0 }}>
            Validation Dashboard
          </h1>
          <p style={{ color: 'var(--text-2)', margin: '4px 0 0 0' }}>
            Monitor your file validation success rates and overall activity.
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

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24, alignItems: 'start' }}>
        {/* Main Chart Area */}
        <div className="card" style={{ padding: 24, height: 480, display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-1)', marginBottom: 24, margin: 0 }}>
            Validation Trends
          </h3>
          <div style={{ flex: 1, minHeight: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
                  tick={{ fill: 'var(--text-3)', fontSize: 12 }}
                  interval={filterType === 'daily' ? 2 : 'preserveStartEnd'}
                  minTickGap={filterType === 'daily' ? 20 : 30}
                  angle={filterType === 'daily' ? -45 : 0}
                  textAnchor={filterType === 'daily' ? 'end' : 'middle'}
                  dy={10}
                />
                <YAxis 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: 'var(--text-3)', fontSize: 12 }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend iconType="circle" wrapperStyle={{ paddingTop: 20 }} />
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
    </div>
  )
}
