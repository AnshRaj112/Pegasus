import { render, screen } from '~/utils/renderWithProviders'

import { activeReportsSuccess, mockActiveReport, reportStateWithActiveData } from '../../Report.mockData'
import { Active } from '../../step/Active'

describe('Active', () => {
  it('displays active reports from the store', () => {
    render(<Active />, { preloadedState: { report: reportStateWithActiveData } })

    expect(screen.getByText('source.csv')).toBeInTheDocument()
    expect(screen.getByText('target.csv')).toBeInTheDocument()
    expect(screen.getByText('Validating…')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('keeps visible rows while refreshing when active reports already exist', () => {
    render(<Active />, {
      preloadedState: {
        report: {
          ...reportStateWithActiveData,
          activeReports: {
            ...activeReportsSuccess,
            isFetching: true,
          },
        },
      },
    })

    expect(screen.getByText('source.csv')).toBeInTheDocument()
    expect(screen.queryByText('Loading active reports...')).not.toBeInTheDocument()
  })

  it('shows loading message while active reports are fetching', () => {
    render(<Active />, {
      preloadedState: {
        report: {
          ...reportStateWithActiveData,
          activeReports: {
            ...activeReportsSuccess,
            data: [],
            isFetching: true,
          },
        },
      },
    })

    expect(screen.getByText('Loading active reports...')).toBeInTheDocument()
  })

  it('shows empty state when no active reports exist', () => {
    render(<Active />, {
      preloadedState: {
        report: {
          ...reportStateWithActiveData,
          activeReports: {
            ...activeReportsSuccess,
            data: [],
          },
        },
      },
    })

    expect(screen.getByText('No active reports found.')).toBeInTheDocument()
  })

  it('filters reports when search query is set in the store', () => {
    render(<Active />, {
      preloadedState: {
        report: {
          ...reportStateWithActiveData,
          activeReports: {
            ...activeReportsSuccess,
            data: [
              mockActiveReport,
              {
                ...mockActiveReport,
                id: 'pair-2',
                sourceTitle: 'other-source.csv',
                jobTitle: 'other-target.csv',
              },
            ],
          },
          searchQuery: 'other-source',
        },
      },
    })

    expect(screen.getByText('other-source.csv')).toBeInTheDocument()
    expect(screen.queryByText('source.csv')).not.toBeInTheDocument()
  })
})
