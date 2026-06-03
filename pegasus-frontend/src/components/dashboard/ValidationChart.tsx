import React from 'react'
import { Card, Select } from 'antd'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'

interface ValidationChartProps {
  data: any[]
  onFilterChange?: (filter: string) => void
  onDateRangeChange?: (dates: any) => void
}

export const ValidationChart: React.FC<ValidationChartProps> = ({
  data,
  onFilterChange,
  onDateRangeChange,
}) => {
  return (
    <Card
      title="Validation Trends"
      extra={
        <Select
          defaultValue="7d"
          style={{ width: 120 }}
          onChange={onFilterChange}
          options={[
            { label: 'Last 7 Days', value: '7d' },
            { label: 'Last 30 Days', value: '30d' },
            { label: 'Last 90 Days', value: '90d' },
          ]}
        />
      }
    >
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="colorPass" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#52c41a" stopOpacity={0.8} />
              <stop offset="95%" stopColor="#52c41a" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorFail" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ba1a1a" stopOpacity={0.8} />
              <stop offset="95%" stopColor="#ba1a1a" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="timestamp" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Area
            type="monotone"
            dataKey="passed"
            stroke="#52c41a"
            fillOpacity={1}
            fill="url(#colorPass)"
            name="Passed"
          />
          <Area
            type="monotone"
            dataKey="failed"
            stroke="#ba1a1a"
            fillOpacity={1}
            fill="url(#colorFail)"
            name="Failed"
          />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  )
}
