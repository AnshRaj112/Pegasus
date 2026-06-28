import { render, screen } from '~/utils/renderWithProviders'

import { MetricsPanel } from '../../components/MetricsPanel'

describe('MetricsPanel', () => {
  it('renders all metric labels', () => {
    render(<MetricsPanel runningCount={1} passed={355} failed={25} totalValidated={380} />)

    expect(screen.getByText('Pass')).toBeInTheDocument()
    expect(screen.getByText('Fail')).toBeInTheDocument()
    expect(screen.getByText('Total Validated')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
    expect(screen.getAllByText('Last 7 days').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('Completed runs')).toBeInTheDocument()
  })

  it('shows formatted metric values', () => {
    render(<MetricsPanel runningCount={2} passed={355} failed={25} totalValidated={380} />)

    expect(screen.getByText('355')).toBeInTheDocument()
    expect(screen.getByText('25')).toBeInTheDocument()
    expect(screen.getByText('380')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('shows loading placeholders while data is fetching', () => {
    render(<MetricsPanel runningCount={0} passed={0} failed={0} totalValidated={0} isLoading />)

    expect(screen.getAllByText('…').length).toBeGreaterThan(0)
  })
})
