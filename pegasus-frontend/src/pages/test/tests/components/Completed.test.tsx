import { render, screen } from '~/utils/renderWithProviders'

import { completedTestsSuccess } from '../../Test.mockdata'
import { initialState } from '../../Test.reducer'
import CompletedView from '../../components/Completed'

const testStateWithCompletedData = {
  ...initialState,
  completedTests: completedTestsSuccess,
}

describe('CompletedView', () => {
  it('displays completed tests from the store', () => {
    render(<CompletedView />, { preloadedState: { test: testStateWithCompletedData } })

    expect(screen.getByText('transaction_log_validation')).toBeInTheDocument()
    expect(screen.getByText('customer_integrity_check')).toBeInTheDocument()
    expect(screen.getByText('schema_drift_detection')).toBeInTheDocument()
    expect(screen.getByText('Incoherent')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /snippet/i })).toHaveLength(3)
  })

  it('shows skeleton loading state while completed tests are fetching', () => {
    render(<CompletedView />, {
      preloadedState: {
        test: {
          ...testStateWithCompletedData,
          completedTests: {
            ...completedTestsSuccess,
            data: [],
            isFetching: true,
          },
        },
      },
    })

    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument()
  })

  it('shows empty state when no completed tests exist', () => {
    render(<CompletedView />, {
      preloadedState: {
        test: {
          ...testStateWithCompletedData,
          completedTests: {
            ...completedTestsSuccess,
            data: [],
          },
        },
      },
    })

    expect(screen.getByText('No completed tests found.')).toBeInTheDocument()
  })

  it('renders pass and fail result badges', () => {
    render(<CompletedView />, { preloadedState: { test: testStateWithCompletedData } })

    expect(screen.getByText(/14 sec Pass/)).toBeInTheDocument()
    expect(screen.getByText(/22 sec Fail/)).toBeInTheDocument()
  })
})
