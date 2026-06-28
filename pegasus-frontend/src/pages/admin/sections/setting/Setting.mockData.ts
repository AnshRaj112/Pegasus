import { AxiosError, AxiosHeaders } from 'axios'

import { initializeNullState } from '~/shared/constants/common.constants'

import { ValidationSettings, ValidationSettingsResponse } from './Setting.interface'
import { initialState } from './Setting.reducer'

export const mockValidationSettings: ValidationSettings = {
  cores: 8,
  autoTuning: true,
  samplesPerColumnError: 10,
}

export const mockValidationSettingsResponse: ValidationSettingsResponse = {
  ...mockValidationSettings,
}

export const mockAxiosError = new AxiosError(
  'Server error',
  'ERR_BAD_REQUEST',
  undefined,
  undefined,
  {
    status: 500,
    statusText: 'Internal Server Error',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: { message: 'Failed to fetch Pegasus settings.' },
  },
)

export const fetchSettingsLoading = {
  ...initialState,
  fetchSettingsState: {
    ...initializeNullState,
    isFetching: true,
  },
}

export const fetchSettingsSuccess = {
  ...initialState,
  fetchSettingsState: {
    ...initializeNullState,
    data: mockValidationSettingsResponse,
  },
}

export const fetchSettingsError = {
  ...initialState,
  fetchSettingsState: {
    ...initializeNullState,
    error: 'Failed to fetch Pegasus settings.',
  },
}

export const saveSettingsLoading = {
  ...fetchSettingsSuccess,
  saveSettingsState: {
    ...initializeNullState,
    isFetching: true,
  },
}

export const saveSettingsError = {
  ...fetchSettingsSuccess,
  saveSettingsState: {
    ...initializeNullState,
    error: 'Failed to save settings.',
  },
}
