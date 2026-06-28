import { render, screen } from '~/utils/renderWithProviders'

import { mockDailyStats } from '../../Dashboard.mockData'
import { PerformanceChartPanel } from '../../components/PerformanceChartPanel'

describe('PerformanceChartPanel', () => {
  it('renders the chart title and legend', () => {
    render(<PerformanceChartPanel dailyStats={mockDailyStats} />)

    expect(screen.getByRole('heading', { name: 'Validation Performance' })).toBeInTheDocument()
    expect(screen.getByText('Pass vs fail (last 7 days)')).toBeInTheDocument()
    expect(screen.getByText('Pass')).toBeInTheDocument()
    expect(screen.getByText('Fail')).toBeInTheDocument()
  })

  it('renders day labels from daily stats', () => {
    render(<PerformanceChartPanel dailyStats={mockDailyStats} />)

    expect(document.querySelector('svg')).toBeInTheDocument()
  })

  it('shows loading subtitle while fetching', () => {
    render(<PerformanceChartPanel dailyStats={[]} isLoading />)

    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('shows empty state when there is no validation history', () => {
    render(<PerformanceChartPanel dailyStats={[]} />)

    expect(screen.getByText('No validation history yet. Run a validation to see trends.')).toBeInTheDocument()
  })
})
