import userEvent from '@testing-library/user-event'
import { beforeEach, vi } from 'vitest'

import { fireEvent, render, screen } from '~/utils/renderWithProviders'

import { validationStateStep3Ready } from '../../Validation.mockData'
import { ConfigureMappingStep } from '../../steps/ConfigureMappingStep'

describe('ConfigureMappingStep', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the mapping header and source/target paths', () => {
    render(<ConfigureMappingStep />, {
      preloadedState: { validation: validationStateStep3Ready },
    })

    expect(screen.getByRole('heading', { name: 'Pegasus_Data_Mapping' })).toBeInTheDocument()
    expect(screen.getByText(/Source:/)).toBeInTheDocument()
    expect(screen.getByText(/Target:/)).toBeInTheDocument()
    expect(screen.getByText('gs://test-bucket/data/source.csv')).toBeInTheDocument()
    expect(screen.getByText('gs://test-bucket/data/target.csv')).toBeInTheDocument()
  })

  it('renders delimiter controls and hydrated column mappings', () => {
    render(<ConfigureMappingStep />, {
      preloadedState: { validation: validationStateStep3Ready },
    })

    expect(screen.getByText('Delimiter')).toBeInTheDocument()
    expect(screen.getByDisplayValue('auto')).toBeInTheDocument()
    expect(screen.getByLabelText('Header row')).toBeChecked()
    expect(screen.getByRole('button', { name: /Configured \(2\)/ })).toBeInTheDocument()
  })

  it('updates delimiter in the store when delimiter input changes', () => {
    const { store } = render(<ConfigureMappingStep />, {
      preloadedState: { validation: validationStateStep3Ready },
    })

    const delimiterInput = screen.getByDisplayValue('auto')
    fireEvent.change(delimiterInput, { target: { value: ',' } })

    expect(store.getState().validation.validationForm.delimiter).toBe(',')
  })

  it('updates hasHeader in the store when header checkbox is toggled', async () => {
    const user = userEvent.setup()
    const { store } = render(<ConfigureMappingStep />, {
      preloadedState: { validation: validationStateStep3Ready },
    })

    await user.click(screen.getByLabelText('Header row'))

    expect(store.getState().validation.validationForm.hasHeader).toBe(false)
  })
})
