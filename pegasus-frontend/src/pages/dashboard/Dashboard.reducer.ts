import { PayloadAction, createSlice } from '@reduxjs/toolkit';

import { initializeNullState } from '~/shared/constants/common.constants';

import { DashboardDataResponse, DashboardReducerState } from './Dashboard.interface';

export const initialState: DashboardReducerState = {
  dashboardDataState: initializeNullState,
  createEntityState: initializeNullState,
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
    createEntityRequest: (state, _action: PayloadAction<{ display_name: string }>) => ({
      ...state,
      createEntityState: {
        ...initializeNullState,
        isFetching: true,
      },
    }),
    createEntitySuccess: (state, action: PayloadAction<string>) => ({
      ...state,
      createEntityState: {
        ...initializeNullState,
        data: action.payload,
      },
    }),
    createEntityError: (state, action: PayloadAction<string>) => ({
      ...state,
      createEntityState: {
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