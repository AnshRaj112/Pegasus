import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type HistoryReducerState, type ValidationLogItem, type MappingLogItem } from './History.interface';

export const initialState: HistoryReducerState = {
  activeTab: 'validation',
  searchQuery: '',
  pageSize: 10,
  validationLogs: {
    data: [],
    total: 0,
    page: 1,
    isFetching: false,
    error: null,
  },
  mappingLogs: {
    data: [],
    total: 0,
    page: 1,
    isFetching: false,
    error: null,
  },
};

const historySlice = createSlice({
  name: 'history',
  initialState,
  reducers: {
    setActiveTab: (state, action: PayloadAction<'validation' | 'mapping'>) => {
      state.activeTab = action.payload;
      state.searchQuery = '';
      if (action.payload === 'validation') {
        state.validationLogs.page = 1;
      } else {
        state.mappingLogs.page = 1;
      }
    },
    setSearchQuery: (state, action: PayloadAction<string>) => {
      state.searchQuery = action.payload;
    },
    setPage: (state, action: PayloadAction<{ tab: 'validation' | 'mapping'; page: number }>) => {
      if (action.payload.tab === 'validation') {
        state.validationLogs.page = action.payload.page;
      } else {
        state.mappingLogs.page = action.payload.page;
      }
    },
    fetchHistoryRequest: (state, action: PayloadAction<{ tab?: 'validation' | 'mapping' } | undefined>) => {
      const tab = action.payload?.tab ?? state.activeTab;
      if (tab === 'validation') {
        state.validationLogs.isFetching = true;
        state.validationLogs.error = null;
      } else {
        state.mappingLogs.isFetching = true;
        state.mappingLogs.error = null;
      }
    },
    fetchValidationLogsSuccess: (
      state,
      action: PayloadAction<{ items: ValidationLogItem[]; total: number }>,
    ) => {
      state.validationLogs.data = action.payload.items;
      state.validationLogs.total = action.payload.total;
      state.validationLogs.isFetching = false;
      state.validationLogs.error = null;
    },
    fetchMappingLogsSuccess: (
      state,
      action: PayloadAction<{ items: MappingLogItem[]; total: number }>,
    ) => {
      state.mappingLogs.data = action.payload.items;
      state.mappingLogs.total = action.payload.total;
      state.mappingLogs.isFetching = false;
      state.mappingLogs.error = null;
    },
    fetchHistoryFailure: (
      state,
      action: PayloadAction<{ tab: 'validation' | 'mapping'; error: string }>,
    ) => {
      if (action.payload.tab === 'validation') {
        state.validationLogs.isFetching = false;
        state.validationLogs.error = action.payload.error;
      } else {
        state.mappingLogs.isFetching = false;
        state.mappingLogs.error = action.payload.error;
      }
    },
    deleteValidationLog: (state, action: PayloadAction<string>) => {
      state.validationLogs.data = state.validationLogs.data.filter((log) => log.id !== action.payload);
      state.validationLogs.total = Math.max(0, state.validationLogs.total - 1);
    },
    deleteMappingLog: (state, action: PayloadAction<string>) => {
      state.mappingLogs.data = state.mappingLogs.data.filter((log) => log.id !== action.payload);
      state.mappingLogs.total = Math.max(0, state.mappingLogs.total - 1);
    },
  },
});

export const historyActions = { ...historySlice.actions };
export default historySlice.reducer;
