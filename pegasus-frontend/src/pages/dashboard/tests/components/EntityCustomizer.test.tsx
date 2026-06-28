import userEvent from '@testing-library/user-event'
import { beforeEach, vi } from 'vitest'

import { render, screen } from '~/utils/renderWithProviders'

import { dashboardDataSuccess, mockEntityInsight, mockEntityInsightBeta } from '../../Dashboard.mockData'
import { EntityCustomizer } from '../../components/EntityCustomizer'

describe('EntityCustomizer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the customizer title and entity selector', () => {
    render(<EntityCustomizer entities={[mockEntityInsight, mockEntityInsightBeta]} />, {
      preloadedState: { dashboard: dashboardDataSuccess },
    })

    expect(screen.getByText('Entity Customizer')).toBeInTheDocument()
    expect(screen.getByText('Entity Selector')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Search entities...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create micro-dashboard/i })).toBeInTheDocument()
  })

  it('filters entity selector options when searching', async () => {
    const user = userEvent.setup()
    render(<EntityCustomizer entities={[mockEntityInsight, mockEntityInsightBeta]} />, {
      preloadedState: { dashboard: dashboardDataSuccess },
    })

    const searchInput = screen.getByPlaceholderText('Search entities...')
    await user.clear(searchInput)
    await user.type(searchInput, 'Beta')

    const optionLabels = screen.getAllByRole('option').map((option) => option.textContent ?? '')
    expect(optionLabels.some((label) => label.includes('Beta Inc'))).toBe(true)
    expect(optionLabels.some((label) => label.includes('Acme Corp'))).toBe(false)
  })

  it('dispatches createEntityRequest when create micro-dashboard is clicked', async () => {
    const user = userEvent.setup()
    const { store } = render(<EntityCustomizer entities={[mockEntityInsight, mockEntityInsightBeta]} />, {
      preloadedState: { dashboard: dashboardDataSuccess },
    })

    await user.click(screen.getByRole('button', { name: /create micro-dashboard/i }))

    expect(store.getState().dashboard.createEntityState.isFetching).toBe(true)
  })
})
