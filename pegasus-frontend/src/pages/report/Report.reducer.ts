import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { ReportState, TabType, ReportItem } from './Report.interface';

const initialState: ReportState = {
  activeTab: 'Active',
  searchQuery: '',
  activeReports: [],
  completedReports: [],
  savedReports: [],
  isLoading: false,
  error: null,
};

const reportSlice = createSlice({
  name: 'report',
  initialState,
  reducers: {
    setTab: (state, action: PayloadAction<TabType>) => {
      state.activeTab = action.payload;
    },
    setSearchQuery: (state, action: PayloadAction<string>) => {
      state.searchQuery = action.payload;
    },
    fetchReportsRequest: (state) => {
      state.isLoading = true;
      state.error = null;
    },
    fetchReportsSuccess: (state, action: PayloadAction<{ tab: TabType; data: ReportItem[] }>) => {
      state.isLoading = false;
      if (action.payload.tab === 'Active') state.activeReports = action.payload.data;
      if (action.payload.tab === 'Completed') state.completedReports = action.payload.data;
      if (action.payload.tab === 'Saved') state.savedReports = action.payload.data;
    },
    fetchReportsFailure: (state, action: PayloadAction<string>) => {
      state.isLoading = false;
      state.error = action.payload;
    },
  },
});

export const reportActions = reportSlice.actions;
export const reportReducer = reportSlice.reducer;