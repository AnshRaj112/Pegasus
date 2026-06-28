import { render, screen } from '~/utils/renderWithProviders'

import { validationStateStep1Ready, validationStateStep2Ready } from '../../Validation.mockData'
import { MappingOverviewStep } from '../../steps/MappingOverviewStep'

describe('MappingOverviewStep', () => {
  it('shows analyzing state when overview profiles are not cached yet', () => {
    render(<MappingOverviewStep />, {
      preloadedState: { validation: validationStateStep1Ready },
    })

    expect(screen.getByText('Source')).toBeInTheDocument()
    expect(screen.getByText('Target')).toBeInTheDocument()
    expect(screen.getByText('Analyzing files')).toBeInTheDocument()
    expect(screen.getByText('Detecting format and estimating file shape…')).toBeInTheDocument()
  })

  it('shows ready state when source and target profiles are loaded', () => {
    render(<MappingOverviewStep />, {
      preloadedState: { validation: validationStateStep2Ready },
    })

    expect(screen.getByText('source.csv')).toBeInTheDocument()
    expect(screen.getByText('target.csv')).toBeInTheDocument()
    expect(screen.getByText('Ready for mapping')).toBeInTheDocument()
    expect(screen.getByText('GCS source and target objects are selected.')).toBeInTheDocument()
  })

  it('renders source and target profile stats from cached profiles', () => {
    render(<MappingOverviewStep />, {
      preloadedState: { validation: validationStateStep2Ready },
    })

    expect(screen.getByText('gs://test-bucket/data/source.csv')).toBeInTheDocument()
    expect(screen.getByText('gs://test-bucket/data/target.csv')).toBeInTheDocument()
    expect(screen.getAllByText('100').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('5').length).toBeGreaterThanOrEqual(2)
  })
})
