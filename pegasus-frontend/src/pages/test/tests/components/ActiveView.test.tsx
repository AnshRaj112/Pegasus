import { render, screen } from '~/utils/renderWithProviders'

import { activeTestsSuccess, testStateWithActiveData } from '../../Test.mockdata'
import ActiveView from '../../components/ActiveView'

describe('ActiveView', () => {
  it('displays active tests from the store', () => {
    render(<ActiveView />, { preloadedState: { test: testStateWithActiveData } })

    expect(screen.getByText('EMPLOYEES')).toBeInTheDocument()
    expect(screen.getByText('SALES_DATA_V4')).toBeInTheDocument()
    expect(screen.getByText('INVENTORY_SNAPSHOT')).toBeInTheDocument()
    expect(screen.getAllByText('Running')).toHaveLength(2)
    expect(screen.getByText('Scheduled')).toBeInTheDocument()
  })

  it('shows skeleton loading state while active tests are fetching', () => {
    render(<ActiveView />, {
      preloadedState: {
        test: {
          ...testStateWithActiveData,
          activeTests: {
            ...activeTestsSuccess,
            data: [],
            isFetching: true,
          },
        },
      },
    })

    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument()
  })

  it('shows empty state when no active tests exist', () => {
    render(<ActiveView />, {
      preloadedState: {
        test: {
          ...testStateWithActiveData,
          activeTests: {
            ...activeTestsSuccess,
            data: [],
          },
        },
      },
    })

    expect(screen.getByText('No active tests found.')).toBeInTheDocument()
  })
})
