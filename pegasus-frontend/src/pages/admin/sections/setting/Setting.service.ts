import axios from 'axios'

import { PELICAN_BASE_PATH, SERVICE_ENDPOINT } from '../../../../shared/constants/service-endpoints.constants'

import { ValidationSettings, ValidationSettingsResponse } from './Setting.interface'

export const SettingServiceApi = {
	fetchValidationSettings: () => {
		return axios.get<ValidationSettingsResponse>(`${PELICAN_BASE_PATH}${SERVICE_ENDPOINT.FILE_VALIDATION_SETTINGS}`)
	},

	saveValidationSettings: (payload: ValidationSettings) => {
		return axios.put<ValidationSettingsResponse>(`${PELICAN_BASE_PATH}${SERVICE_ENDPOINT.FILE_VALIDATION_SETTINGS}`, payload)
	},
}