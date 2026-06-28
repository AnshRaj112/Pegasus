import userEvent from '@testing-library/user-event'
import { beforeEach, vi } from 'vitest'

import { render, screen, waitFor } from '~/utils/renderWithProviders'

import TestView from '../TestView'
import { testStateWithActiveData } from '../Test.mockdata'

describe('TestView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the tests page header, search input, and tabs', () => {
    render(<TestView />)

    expect(screen.getByRole('heading', { name: 'Tests' })).toBeInTheDocument()
    expect(screen.getByTestId('tests-search-input')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Search by Test or Group Name')).toBeInTheDocument()
    expect(screen.getByTestId('tab-active')).toBeInTheDocument()
    expect(screen.getByTestId('tab-completed')).toBeInTheDocument()
    expect(screen.getByTestId('tab-saved')).toBeInTheDocument()
  })

  it('dispatches fetchActiveTestsRequest on mount', async () => {
    const view = render(<TestView />, { preloadedState: { test: testStateWithActiveData } })

    await waitFor(() => {
      expect(view.store.getState().test.activeTests.isFetching).toBe(true)
    })
  })

  it('dispatches fetchCompletedTestsRequest when completed tab is clicked', async () => {
    const user = userEvent.setup()
    const { store } = render(<TestView />, { preloadedState: { test: testStateWithActiveData } })

    await user.click(screen.getByTestId('tab-completed'))

    expect(store.getState().test.completedTests.isFetching).toBe(true)
  })

  it('dispatches fetchSavedTestsRequest when saved tab is clicked', async () => {
    const user = userEvent.setup()
    const { store } = render(<TestView />, { preloadedState: { test: testStateWithActiveData } })

    await user.click(screen.getByTestId('tab-saved'))

    expect(store.getState().test.savedTests.isFetching).toBe(true)
  })
})
