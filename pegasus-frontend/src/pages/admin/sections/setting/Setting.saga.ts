import { PayloadAction } from '@reduxjs/toolkit'
import { notification } from 'antd'
import { AxiosError, AxiosResponse } from 'axios'
import { all, call, put, takeLatest } from 'redux-saga/effects'

import { NOTIFICATION_SERVICE_TYPES } from '../../../../shared/constants/common.constant'

import { ValidationSettings, ValidationSettingsResponse } from './Setting.interface'
import { settingActions } from './Setting.reducer'
import { SettingServiceApi } from './Setting.service'

export function* fetchSettingsSaga() {
	try {
		const response: AxiosResponse<ValidationSettingsResponse> = yield call(SettingServiceApi.fetchValidationSettings)
		yield put(settingActions.fetchSettingsSuccess(response.data))
	} catch (error) {
		if (error instanceof AxiosError) {
			const errorMessage = error.response?.data?.message || 'Failed to fetch Pegasus settings.'
			yield put(settingActions.fetchSettingsError(errorMessage))
			notification.error({
				message: NOTIFICATION_SERVICE_TYPES.ERROR,
				description: errorMessage,
			})
		}
	}
}

export function* saveSettingsSaga(action: PayloadAction<ValidationSettings>) {
	try {
		const response: AxiosResponse<ValidationSettingsResponse> = yield call(
			SettingServiceApi.saveValidationSettings,
			action.payload
		)
		yield put(settingActions.saveSettingsSuccess(response.data))
		notification.success({
			message: 'Success',
			description: 'Settings saved successfully.',
		})
	} catch (error) {
		if (error instanceof AxiosError) {
			const errorMessage = error.response?.data?.message || 'Failed to save settings.'
			yield put(settingActions.saveSettingsError(errorMessage))
			notification.error({
				message: NOTIFICATION_SERVICE_TYPES.ERROR,
				description: errorMessage,
			})
		}
	}
}

export function* settingSaga() {
	yield all([
		takeLatest(settingActions.fetchSettingsRequest.type, fetchSettingsSaga),
		takeLatest(settingActions.saveSettingsRequest.type, saveSettingsSaga),
	])
}