import React, { useState, useMemo } from 'react'
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

const { Option } = Select
const { RangePicker } = DatePicker

// Generate some mock data for the last 30 days
const generateMockData = (days) => {
  const data = []
  let today = dayjs()
  for (let i = days - 1; i >= 0; i--) {
    const passed = Math.floor(Math.random() * 50) + 20
    const failed = Math.floor(Math.random() * 10) + 1
    data.push({
      date: today.subtract(i, 'day').format('MMM DD'),
      fullDate: today.subtract(i, 'day').format('YYYY-MM-DD'),
      passed,
      failed,
      total: passed + failed
    })
  }
  return data
}

const mockDataWeekly = generateMockData(7)
const mockDataMonthly = generateMockData(30)
// For custom we just slice from monthly or generate more
const mockDataCustom = generateMockData(14)

export default function Dashboard() {
  const [filterType, setFilterType] = useState('weekly')
  const [dateRange, setDateRange] = useState(null)

  // Determine which data to show based on filter
  const currentData = useMemo(() => {
    if (filterType === 'weekly') return mockDataWeekly
    if (filterType === 'monthly') return mockDataMonthly
    if (filterType === 'custom') return mockDataCustom // In a real app, filter based on dateRange
    return mockDataWeekly
  }, [filterType, dateRange])

  // Calculate totals
  const totals = useMemo(() => {
    return currentData.reduce(
      (acc, curr) => ({
        passed: acc.passed + curr.passed,
        failed: acc.failed + curr.failed,
        total: acc.total + curr.total
      }),
      { passed: 0, failed: 0, total: 0 }
    )
  }, [currentData])

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
              <AreaChart data={currentData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
                {((totals.passed / totals.total) * 100).toFixed(1)}% success rate
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
                {((totals.failed / totals.total) * 100).toFixed(1)}% failure rate
              </p>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
