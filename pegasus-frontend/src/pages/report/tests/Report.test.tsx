import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, vi } from 'vitest'

import { render, screen, waitFor } from '~/utils/renderWithProviders'

import Report from '../Report'
import { reportStateWithActiveData } from '../Report.mockData'

describe('Report', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'setInterval').mockReturnValue(0 as unknown as ReturnType<typeof setInterval>)
    vi.spyOn(globalThis, 'clearInterval').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the report page header and tabs', () => {
    render(<Report />)

    expect(screen.getByRole('heading', { name: 'Validation Reports' })).toBeInTheDocument()
    expect(screen.getByText('Manage and monitor your data validation tests.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Active' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Completed' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Saved' })).toBeInTheDocument()
  })

  it('renders the search input with placeholder text', () => {
    render(<Report />)

    expect(screen.getByPlaceholderText('Search by Test or Group Name')).toBeInTheDocument()
  })

  it('dispatches fetchReportsRequest on mount without hiding existing active rows', async () => {
    const view = render(<Report />, { preloadedState: { report: reportStateWithActiveData } })

    await waitFor(() => {
      expect(view.store.getState().report.activeReports.isFetching).toBe(false)
      expect(view.store.getState().report.activeReports.data).toHaveLength(1)
    })
  })

  it('does not start polling when there are no active rows', () => {
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval')

    render(<Report />)

    expect(setIntervalSpy).not.toHaveBeenCalled()
  })

  it('starts polling when active rows are present', () => {
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval')

    render(<Report />, { preloadedState: { report: reportStateWithActiveData } })

    expect(setIntervalSpy).toHaveBeenCalled()
  })

  it('switches active tab when a tab button is clicked', async () => {
    const user = userEvent.setup()
    const { store } = render(<Report />, { preloadedState: { report: reportStateWithActiveData } })

    await user.click(screen.getByRole('button', { name: 'Completed' }))
    expect(store.getState().report.activeTab).toBe('Completed')

    await user.click(screen.getByRole('button', { name: 'Saved' }))
    expect(store.getState().report.activeTab).toBe('Saved')
  })

  it('updates search query in the store when typing in the search input', async () => {
    const user = userEvent.setup()
    const { store } = render(<Report />, { preloadedState: { report: reportStateWithActiveData } })

    await user.type(screen.getByPlaceholderText('Search by Test or Group Name'), 'acme')

    expect(store.getState().report.searchQuery).toBe('acme')
  })
})
