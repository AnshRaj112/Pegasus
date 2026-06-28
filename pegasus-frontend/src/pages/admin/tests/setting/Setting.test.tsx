import userEvent from '@testing-library/user-event'
import { beforeEach, vi } from 'vitest'

import { render, screen, waitFor } from '~/utils/renderWithProviders'

import Setting from '../../sections/setting/Setting'
import { fetchSettingsSuccess, mockValidationSettingsResponse } from '../../sections/setting/Setting.mockData'
import { settingActions } from '../../sections/setting/Setting.reducer'

const prepareSettingView = async () => {
  const view = render(<Setting />, { preloadedState: { setting: fetchSettingsSuccess } })

  await waitFor(() => {
    expect(view.store.getState().setting.fetchSettingsState.isFetching).toBe(true)
  })

  view.store.dispatch(settingActions.fetchSettingsSuccess(mockValidationSettingsResponse))

  await waitFor(() => {
    expect(view.store.getState().setting.fetchSettingsState.isFetching).toBe(false)
  })

  return view
}

describe('Setting', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the settings form with default fields', async () => {
    await prepareSettingView()

    expect(screen.getByText('Pegasus Settings')).toBeInTheDocument()
    expect(screen.getByTestId('input-cores')).toBeInTheDocument()
    expect(screen.getByTestId('checkbox-autotune')).toBeInTheDocument()
    expect(screen.getByTestId('select-samples')).toBeInTheDocument()
    expect(screen.getByTestId('button-reset')).toBeInTheDocument()
    expect(screen.getByTestId('button-save')).toBeInTheDocument()
    expect(screen.getByTestId('section-engine-info')).toBeInTheDocument()
  })

  it('populates form fields from loaded settings data', async () => {
    await prepareSettingView()

    await waitFor(() => {
      expect(screen.getByTestId('input-cores')).toHaveValue('8')
    })
    expect(screen.getByTestId('checkbox-autotune')).toBeChecked()
  })

  it('dispatches saveSettingsRequest when save is clicked', async () => {
    const user = userEvent.setup()
    const { store } = await prepareSettingView()

    await user.click(screen.getByTestId('button-save'))

    expect(store.getState().setting.saveSettingsState.isFetching).toBe(true)
  })

  it('resets form to defaults when reset is clicked', async () => {
    const user = userEvent.setup()
    const view = render(<Setting />, {
      preloadedState: {
        setting: {
          ...fetchSettingsSuccess,
          fetchSettingsState: {
            ...fetchSettingsSuccess.fetchSettingsState,
            data: { cores: 16, autoTuning: false, samplesPerColumnError: 50 },
          },
        },
      },
    })

    await waitFor(() => {
      expect(view.store.getState().setting.fetchSettingsState.isFetching).toBe(true)
    })

    view.store.dispatch(
      settingActions.fetchSettingsSuccess({ cores: 16, autoTuning: false, samplesPerColumnError: 50 }),
    )

    await waitFor(() => {
      expect(screen.getByTestId('input-cores')).toHaveValue('16')
      expect(view.store.getState().setting.fetchSettingsState.isFetching).toBe(false)
    })

    await user.click(screen.getByTestId('button-reset'))

    await waitFor(() => {
      expect(screen.getByTestId('input-cores')).toHaveValue('8')
    })
    expect(screen.getByTestId('checkbox-autotune')).toBeChecked()
  })

  it('shows loading spinner while settings are being fetched', () => {
    render(<Setting />, {
      preloadedState: {
        setting: {
          ...fetchSettingsSuccess,
          fetchSettingsState: {
            ...fetchSettingsSuccess.fetchSettingsState,
            isFetching: true,
          },
        },
      },
    })

    expect(screen.getByTestId('spinner-settings-loading')).toHaveClass('ant-spin-spinning')
  })
})
