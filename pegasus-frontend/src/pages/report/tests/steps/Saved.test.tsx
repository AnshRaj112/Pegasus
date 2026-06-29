import userEvent from '@testing-library/user-event'
import { beforeEach, vi } from 'vitest'

import { render, screen } from '~/utils/renderWithProviders'

import { mockSavedReport, savedReportsSuccess } from '../../Report.mockData'
import { initialState } from '../../Report.reducer'
import { Saved } from '../../step/Saved'

const reportStateWithSavedData = {
  ...initialState,
  activeTab: 'Saved' as const,
  savedReports: savedReportsSuccess,
}

describe('Saved', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays saved mappings from the store', () => {
    render(<Saved />, { preloadedState: { report: reportStateWithSavedData } })

    expect(screen.getByText('saved-source.csv')).toBeInTheDocument()
    expect(screen.getByText('saved-target.csv')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /run/i })).toBeInTheDocument()
  })

  it('shows loading message while saved mappings are fetching', () => {
    render(<Saved />, {
      preloadedState: {
        report: {
          ...reportStateWithSavedData,
          savedReports: {
            ...savedReportsSuccess,
            data: [],
            isFetching: true,
          },
        },
      },
    })

    expect(screen.getByText('Loading saved mappings...')).toBeInTheDocument()
  })

  it('shows empty state when no saved mappings exist', () => {
    render(<Saved />, {
      preloadedState: {
        report: {
          ...reportStateWithSavedData,
          savedReports: {
            ...savedReportsSuccess,
            data: [],
          },
        },
      },
    })

    expect(screen.getByText('No saved mappings found.')).toBeInTheDocument()
  })

  it('dispatches runValidationFromHistoryRequest when Run is clicked', async () => {
    const user = userEvent.setup()
    const { store } = render(<Saved />, { preloadedState: { report: reportStateWithSavedData } })

    await user.click(screen.getByRole('button', { name: /run/i }))

    expect(store.getState().validation.validationDataState.isFetching).toBe(true)
  })

  it('filters saved mappings when search query is set in the store', () => {
    render(<Saved />, {
      preloadedState: {
        report: {
          ...reportStateWithSavedData,
          savedReports: {
            ...savedReportsSuccess,
            data: [
              mockSavedReport,
              {
                ...mockSavedReport,
                id: 'saved-pair-2',
                sourceTitle: 'other-saved.csv',
                jobTitle: 'other-target.csv',
              },
            ],
          },
          searchQuery: 'other-saved',
        },
      },
    })

    expect(screen.getByText('other-saved.csv')).toBeInTheDocument()
    expect(screen.queryByText('saved-source.csv')).not.toBeInTheDocument()
  })
})
