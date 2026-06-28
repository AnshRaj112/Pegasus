import { render, screen } from '~/utils/renderWithProviders'

import { mockSavedTests, savedTestsSuccess } from '../../Test.mockdata'
import { initialState } from '../../Test.reducer'
import SavedView from '../../components/SavedView'

const testStateWithSavedData = {
  ...initialState,
  savedTests: savedTestsSuccess,
}

describe('SavedView', () => {
  it('displays saved draft tests from the store', () => {
    render(<SavedView />, { preloadedState: { test: testStateWithSavedData } })

    expect(screen.getByText('Standard Load Performance Analysis')).toBeInTheDocument()
    expect(screen.getByText('Cloud Latency Stress Test (B)')).toBeInTheDocument()
    expect(screen.getAllByText('Draft')).toHaveLength(2)
  })

  it('shows skeleton loading state while saved tests are fetching', () => {
    render(<SavedView />, {
      preloadedState: {
        test: {
          ...testStateWithSavedData,
          savedTests: {
            ...savedTestsSuccess,
            data: [],
            isFetching: true,
          },
        },
      },
    })

    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument()
  })

  it('shows empty state when no saved tests exist', () => {
    render(<SavedView />, {
      preloadedState: {
        test: {
          ...testStateWithSavedData,
          savedTests: {
            ...savedTestsSuccess,
            data: [],
          },
        },
      },
    })

    expect(screen.getByText('No saved tests found.')).toBeInTheDocument()
  })

  it('renders schedule details for each saved test', () => {
    render(<SavedView />, { preloadedState: { test: testStateWithSavedData } })

    expect(screen.getByText('Ref: EMEA_Q4_Optimization')).toBeInTheDocument()
    expect(screen.getByText('Scheduled for next maintenance window')).toBeInTheDocument()
    expect(screen.getByText(mockSavedTests[0].subtitle)).toBeInTheDocument()
  })
})
