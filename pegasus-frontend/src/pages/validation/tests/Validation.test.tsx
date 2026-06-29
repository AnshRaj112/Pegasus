import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, vi } from 'vitest'

import { render, screen } from '~/utils/renderWithProviders'

import ValidationWizardView from '../ValidationWizardView'
import { validationStateStep1Ready, validationStateWithConnections } from '../Validation.mockData'

vi.mock('../validationTabStorage', () => ({
  loadValidationTabSession: vi.fn(() => null),
  saveValidationTabSession: vi.fn(),
}))

vi.mock('../browseCacheStorage', () => ({
  getConnectionBrowsePath: vi.fn(() => null),
  isBrowsePathFresh: vi.fn(() => false),
  setConnectionBrowsePath: vi.fn(),
}))

vi.mock('../validationRerun', async () => {
  const actual = await vi.importActual<typeof import('../validationRerun')>('../validationRerun')
  return {
    ...actual,
    loadValidationRunForm: vi.fn(),
  }
})

vi.mock('antd', () => ({
  notification: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('ValidationWizardView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the wizard header and step tabs on step 1', () => {
    render(<ValidationWizardView />, {
      route: '/validations',
      preloadedState: { validation: validationStateWithConnections },
    })

    expect(screen.getByRole('heading', { name: 'File-to-File Validation Tool' })).toBeInTheDocument()
    expect(screen.getByText('File Selection')).toBeInTheDocument()
    expect(screen.getByText('File Overview')).toBeInTheDocument()
    expect(screen.getByText('File Mapping')).toBeInTheDocument()
  })

  it('renders save draft and proceed actions', () => {
    render(<ValidationWizardView />, {
      route: '/validations',
      preloadedState: { validation: validationStateWithConnections },
    })

    expect(screen.getByRole('button', { name: /save draft/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /proceed to overview/i })).toBeInTheDocument()
  })

  it('disables proceed when step 1 is not valid', () => {
    render(<ValidationWizardView />, {
      route: '/validations',
      preloadedState: { validation: validationStateWithConnections },
    })

    expect(screen.getByRole('button', { name: /proceed to overview/i })).toBeDisabled()
  })

  it('enables proceed when source and target files are selected', () => {
    render(<ValidationWizardView />, {
      route: '/validations',
      preloadedState: { validation: validationStateStep1Ready },
    })

    expect(screen.getByRole('button', { name: /proceed to overview/i })).not.toBeDisabled()
  })

  it('dispatches saveDraftRequest when save draft is clicked with valid files', async () => {
    const user = userEvent.setup()
    const { store } = render(<ValidationWizardView />, {
      route: '/validations',
      preloadedState: { validation: validationStateStep1Ready },
    })

    await user.click(screen.getByRole('button', { name: /save draft/i }))

    expect(store.getState().validation.saveDraftState.isFetching).toBe(true)
    expect(store.getState().validation.saveDraftState.intent).toBe('save')
  })

  it('dispatches only saveDraftRequest when proceeding from step 1 (no parallel preview)', async () => {
    const user = userEvent.setup()
    const { store } = render(<ValidationWizardView />, {
      route: '/validations',
      preloadedState: { validation: validationStateStep1Ready },
    })

    await user.click(screen.getByRole('button', { name: /proceed to overview/i }))

    const state = store.getState().validation
    expect(state.saveDraftState.isFetching).toBe(true)
    expect(state.saveDraftState.intent).toBe('proceed')
    expect(state.previewColumnsState.isFetching).toBe(false)
    expect(state.previewFixedWidthState.isFetching).toBe(false)
    expect(state.overviewProfileFetchState.isFetching).toBe(false)
  })
})
