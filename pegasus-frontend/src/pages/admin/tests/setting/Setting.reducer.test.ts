import settingReducer, { initialState, settingActions } from '../../sections/setting/Setting.reducer'
import {
  fetchSettingsError,
  fetchSettingsLoading,
  fetchSettingsSuccess,
  mockValidationSettings,
  mockValidationSettingsResponse,
  saveSettingsError,
  saveSettingsLoading,
} from '../../sections/setting/Setting.mockData'

describe('Setting reducer', () => {
  it('returns initial state for unknown action', () => {
    expect(settingReducer(undefined, { type: 'unknown' })).toEqual(initialState)
  })

  describe('fetchSettings', () => {
    it('sets loading on fetchSettingsRequest', () => {
      expect(settingReducer(initialState, settingActions.fetchSettingsRequest())).toEqual(fetchSettingsLoading)
    })

    it('stores data on fetchSettingsSuccess', () => {
      expect(
        settingReducer(initialState, settingActions.fetchSettingsSuccess(mockValidationSettingsResponse)),
      ).toEqual(fetchSettingsSuccess)
    })

    it('stores error on fetchSettingsError', () => {
      expect(
        settingReducer(initialState, settingActions.fetchSettingsError('Failed to fetch Pegasus settings.')),
      ).toEqual(fetchSettingsError)
    })
  })

  describe('saveSettings', () => {
    it('sets loading on saveSettingsRequest', () => {
      expect(
        settingReducer(fetchSettingsSuccess, settingActions.saveSettingsRequest(mockValidationSettings)),
      ).toEqual(saveSettingsLoading)
    })

    it('stores data on saveSettingsSuccess and updates fetchSettingsState', () => {
      const result = settingReducer(
        fetchSettingsSuccess,
        settingActions.saveSettingsSuccess(mockValidationSettingsResponse),
      )
      expect(result.saveSettingsState.data).toEqual(mockValidationSettingsResponse)
      expect(result.fetchSettingsState.data).toEqual(mockValidationSettingsResponse)
      expect(result.saveSettingsState.isFetching).toBe(false)
    })

    it('stores error on saveSettingsError', () => {
      expect(
        settingReducer(fetchSettingsSuccess, settingActions.saveSettingsError('Failed to save settings.')),
      ).toEqual(saveSettingsError)
    })
  })

  it('resets to initial state on resetSettingsState', () => {
    expect(settingReducer(fetchSettingsSuccess, settingActions.resetSettingsState())).toEqual(initialState)
  })
})
