import { render, screen } from '~/utils/renderWithProviders'

import { completedReportsSuccess, mockCompletedReport, reportStateWithCompletedData } from '../../Report.mockData'
import { Completed } from '../../step/Completed'

describe('Completed', () => {
  it('displays completed reports from the store', () => {
    render(<Completed />, { preloadedState: { report: reportStateWithCompletedData } })

    expect(screen.getByText('completed-source.csv')).toBeInTheDocument()
    expect(screen.getByText('completed-target.csv')).toBeInTheDocument()
    expect(screen.getByText('Jun 12, 26')).toBeInTheDocument()
  })

  it('shows loading message while completed reports are fetching', () => {
    render(<Completed />, {
      preloadedState: {
        report: {
          ...reportStateWithCompletedData,
          completedReports: {
            ...completedReportsSuccess,
            data: [],
            isFetching: true,
          },
        },
      },
    })

    expect(screen.getByText('Loading completed reports...')).toBeInTheDocument()
  })

  it('shows empty state when no completed reports exist', () => {
    render(<Completed />, {
      preloadedState: {
        report: {
          ...reportStateWithCompletedData,
          completedReports: {
            ...completedReportsSuccess,
            data: [],
          },
        },
      },
    })

    expect(screen.getByText('No completed reports found.')).toBeInTheDocument()
  })

  it('filters reports when search query is set in the store', () => {
    render(<Completed />, {
      preloadedState: {
        report: {
          ...reportStateWithCompletedData,
          completedReports: {
            ...completedReportsSuccess,
            data: [
              mockCompletedReport,
              {
                ...mockCompletedReport,
                id: '2',
                sourceTitle: 'other-completed.csv',
                jobTitle: 'other-target.csv',
              },
            ],
          },
          searchQuery: 'other-completed',
        },
      },
    })

    expect(screen.getByText('other-completed.csv')).toBeInTheDocument()
    expect(screen.queryByText('completed-source.csv')).not.toBeInTheDocument()
  })
})
