import { beforeEach, vi } from 'vitest'

import { render, screen, waitFor } from '~/utils/renderWithProviders'

import Dashboard from '../Dashboard'
import { dashboardDataSuccess, mockDashboardData } from '../Dashboard.mockData'
import { dashboardActions } from '../Dashboard.reducer'

const prepareDashboardView = async () => {
  const view = render(<Dashboard />, { preloadedState: { dashboard: dashboardDataSuccess } })

  await waitFor(() => {
    expect(view.store.getState().dashboard.dashboardDataState.isFetching).toBe(true)
  })

  view.store.dispatch(dashboardActions.fetchDashboardDataSuccess(mockDashboardData))

  await waitFor(() => {
    expect(view.store.getState().dashboard.dashboardDataState.isFetching).toBe(false)
  })

  return view
}

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders chart and metrics after data loads', async () => {
    await prepareDashboardView()

    expect(screen.getByRole('heading', { name: 'Validation Performance' })).toBeInTheDocument()
    expect(screen.getByText('355')).toBeInTheDocument()
    expect(screen.getByText('25')).toBeInTheDocument()
    expect(screen.getByText('380')).toBeInTheDocument()
    expect(screen.getByText('Active processing tasks')).toBeInTheDocument()
  })

  it('dispatches fetchDashboardDataRequest on mount', async () => {
    const view = render(<Dashboard />, { preloadedState: { dashboard: dashboardDataSuccess } })

    await waitFor(() => {
      expect(view.store.getState().dashboard.dashboardDataState.isFetching).toBe(true)
    })
  })
})
