import { beforeEach, vi } from 'vitest'

import { render, screen } from '~/utils/renderWithProviders'

import {
  validationStateStep1Ready,
  validationStateWithConnections,
} from '../../Validation.mockData'
import { FileSelectionStep } from '../../steps/FileSelectionStep'

vi.mock('../../browseCacheStorage', () => ({
  getConnectionBrowsePath: vi.fn(() => null),
  isBrowsePathFresh: vi.fn(() => false),
  setConnectionBrowsePath: vi.fn(),
}))

describe('FileSelectionStep', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the validation pattern selector and GCS connections panel', () => {
    render(<FileSelectionStep />, {
      preloadedState: { validation: validationStateWithConnections },
    })

    expect(screen.getByText('Validation Pattern')).toBeInTheDocument()
    expect(screen.getByRole('combobox')).toHaveValue('Single to Single (Default)')
    expect(screen.getByText('GCS Connections')).toBeInTheDocument()
    expect(screen.getByText('Browsing for Source')).toBeInTheDocument()
  })

  it('shows file selection placeholders when no files are chosen', () => {
    render(<FileSelectionStep />, {
      preloadedState: { validation: validationStateWithConnections },
    })

    expect(screen.getAllByText('Pick a GCS object from any connection…')).toHaveLength(2)
    expect(screen.getByText('1. Source (0)')).toBeInTheDocument()
    expect(screen.getByText('2. Target (0)')).toBeInTheDocument()
  })

  it('shows selected source and target files from the store', () => {
    render(<FileSelectionStep />, {
      preloadedState: { validation: validationStateStep1Ready },
    })

    expect(screen.getByText('1. Source (1)')).toBeInTheDocument()
    expect(screen.getByText('2. Target (1)')).toBeInTheDocument()
    expect(screen.getByText('source.csv')).toBeInTheDocument()
    expect(screen.getByText('target.csv')).toBeInTheDocument()
    expect(screen.getByText('gs://test-bucket/data/source.csv')).toBeInTheDocument()
    expect(screen.getByText('gs://test-bucket/data/target.csv')).toBeInTheDocument()
  })
})
