import { type PayloadAction, createSlice } from '@reduxjs/toolkit';

import { initializeNullState } from '../../shared/constants/common.constant';

import { type DashboardDataResponse, type DashboardReducerState } from './Dashboard.interface';

export const initialState: DashboardReducerState = {
  dashboardDataState: initializeNullState,
};

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState,
  reducers: {
    fetchDashboardDataRequest: (state) => ({
      ...state,
      dashboardDataState: {
        ...initializeNullState,
        isFetching: true,
      },
    }),
    fetchDashboardDataSuccess: (state, action: PayloadAction<DashboardDataResponse>) => ({
      ...state,
      dashboardDataState: {
        ...initializeNullState,
        data: action.payload,
      },
    }),
    fetchDashboardDataError: (state, action: PayloadAction<string>) => ({
      ...state,
      dashboardDataState: {
        ...initializeNullState,
        error: action.payload,
      },
    }),
  },
});

export const dashboardActions = {
  ...dashboardSlice.actions,
};

export default dashboardSlice.reducer;