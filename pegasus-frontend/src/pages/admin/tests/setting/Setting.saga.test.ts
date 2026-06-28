import { all, call, put, takeLatest } from 'redux-saga/effects'
import { AxiosError, AxiosHeaders } from 'axios'
import { afterEach, vi } from 'vitest'

import { mockValidationSettings, mockValidationSettingsResponse } from '../../sections/setting/Setting.mockData'
import { settingActions } from '../../sections/setting/Setting.reducer'
import { fetchSettingsSaga, saveSettingsSaga, settingSaga } from '../../sections/setting/Setting.saga'
import { SettingServiceApi } from '../../sections/setting/Setting.service'

vi.mock('../../sections/setting/Setting.service', () => ({
  SettingServiceApi: {
    fetchValidationSettings: vi.fn(),
    saveValidationSettings: vi.fn(),
  },
}))

vi.mock('antd', () => ({
  notification: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const createAxiosResponse = <T,>(data: T) => ({
  data,
  status: 200,
  statusText: 'OK',
  headers: {},
  config: { headers: new AxiosHeaders() },
})

describe('Setting sagas', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchSettingsSaga', () => {
    it('dispatches success when settings are fetched', () => {
      const iterator = fetchSettingsSaga()
      expect(iterator.next().value).toEqual(call(SettingServiceApi.fetchValidationSettings))
      expect(iterator.next(createAxiosResponse(mockValidationSettingsResponse)).value).toEqual(
        put(settingActions.fetchSettingsSuccess(mockValidationSettingsResponse)),
      )
      expect(iterator.next().done).toBe(true)
    })

    it('dispatches error and notifies when fetch fails with AxiosError', () => {
      const iterator = fetchSettingsSaga()
      iterator.next()
      const axiosError = new AxiosError(
        'Fetch failed',
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
      expect(iterator.throw(axiosError).value).toEqual(
        put(settingActions.fetchSettingsError('Failed to fetch Pegasus settings.')),
      )
    })
  })

  describe('saveSettingsSaga', () => {
    it('dispatches success when settings are saved', () => {
      const action = { type: settingActions.saveSettingsRequest.type, payload: mockValidationSettings }
      const iterator = saveSettingsSaga(action)
      expect(iterator.next().value).toEqual(
        call(SettingServiceApi.saveValidationSettings, mockValidationSettings),
      )
      expect(iterator.next(createAxiosResponse(mockValidationSettingsResponse)).value).toEqual(
        put(settingActions.saveSettingsSuccess(mockValidationSettingsResponse)),
      )
    })

    it('dispatches error when save fails with AxiosError', () => {
      const action = { type: settingActions.saveSettingsRequest.type, payload: mockValidationSettings }
      const iterator = saveSettingsSaga(action)
      iterator.next()
      const axiosError = new AxiosError(
        'Save failed',
        'ERR_BAD_REQUEST',
        undefined,
        undefined,
        {
          status: 500,
          statusText: 'Internal Server Error',
          headers: {},
          config: { headers: new AxiosHeaders() },
          data: { message: 'Failed to save settings.' },
        },
      )
      expect(iterator.throw(axiosError).value).toEqual(
        put(settingActions.saveSettingsError('Failed to save settings.')),
      )
    })
  })

  describe('settingSaga root watcher', () => {
    it('registers takeLatest watchers for fetch and save actions', () => {
      const iterator = settingSaga()
      expect(iterator.next().value).toEqual(
        all([
          takeLatest(settingActions.fetchSettingsRequest.type, fetchSettingsSaga),
          takeLatest(settingActions.saveSettingsRequest.type, saveSettingsSaga),
        ]),
      )
      expect(iterator.next().done).toBe(true)
    })
  })
})
