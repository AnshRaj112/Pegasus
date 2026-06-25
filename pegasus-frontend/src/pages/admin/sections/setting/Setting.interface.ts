export interface ValidationSettings {
	cores: number
	autoTuning: boolean
	samplesPerColumnError: number
}

export interface ValidationSettingsResponse extends ValidationSettings {}

export interface SettingReducerState {
	fetchSettingsState: {
		data: ValidationSettingsResponse | null
		isFetching: boolean
		error: string | null
	}
	saveSettingsState: {
		data: ValidationSettingsResponse | null
		isFetching: boolean
		error: string | null
	}
}