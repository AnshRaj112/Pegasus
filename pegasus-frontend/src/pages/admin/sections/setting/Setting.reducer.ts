import { PayloadAction, createSlice } from '@reduxjs/toolkit'

import { initializeNullState } from '../../../../shared/constants/common.constant'

import { SettingReducerState, ValidationSettings, ValidationSettingsResponse } from './Setting.interface'

export const initialState: SettingReducerState = {
	fetchSettingsState: initializeNullState,
	saveSettingsState: initializeNullState,
}

const settingSlice = createSlice({
	name: 'setting',
	initialState,
	reducers: {
		fetchSettingsRequest: (state) => ({
			...state,
			fetchSettingsState: {
				...initializeNullState,
				isFetching: true,
			},
		}),
		fetchSettingsSuccess: (state, action: PayloadAction<ValidationSettingsResponse>) => ({
			...state,
			fetchSettingsState: {
				...initializeNullState,
				data: action.payload,
			},
		}),
		fetchSettingsError: (state, action: PayloadAction<string>) => ({
			...state,
			fetchSettingsState: {
				...initializeNullState,
				error: action.payload,
			},
		}),
		saveSettingsRequest: (state, _action: PayloadAction<ValidationSettings>) => ({
			...state,
			saveSettingsState: {
				...initializeNullState,
				isFetching: true,
			},
		}),
		saveSettingsSuccess: (state, action: PayloadAction<ValidationSettingsResponse>) => ({
			...state,
			saveSettingsState: {
				...initializeNullState,
				data: action.payload,
			},
			fetchSettingsState: {
				...state.fetchSettingsState,
				data: action.payload,
			},
		}),
		saveSettingsError: (state, action: PayloadAction<string>) => ({
			...state,
			saveSettingsState: {
				...initializeNullState,
				error: action.payload,
			},
		}),
		resetSettingsState: () => initialState,
	},
})

export const settingActions = {
	...settingSlice.actions,
}

export default settingSlice.reducer