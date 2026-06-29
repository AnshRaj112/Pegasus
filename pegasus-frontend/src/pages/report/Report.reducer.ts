import { createSlice, PayloadAction } from '@reduxjs/toolkit';

import { initializeEmptyState } from '~/shared/constants/common.constants';

import { ReportItem, ReportState, TabType } from './Report.interface';
import type { MismatchSampleRow, ValidationHistoryDetail } from '../../shared/api/Api';

type ReportListKey = 'activeReports' | 'completedReports' | 'savedReports';

const tabToListKey = (tab: TabType): ReportListKey => {
  switch (tab) {
    case 'Active':
      return 'activeReports';
    case 'Completed':
      return 'completedReports';
    case 'Saved':
      return 'savedReports';
  }
};

export const initialState: ReportState = {
  activeTab: 'Active',
  searchQuery: '',
  activeReports: initializeEmptyState,
  completedReports: initializeEmptyState,
  savedReports: initializeEmptyState,
  historyRunState: {
    runId: null,
    data: null,
    isFetching: false,
    error: null,
  },
  mismatchesState: {
    runId: null,
    items: [],
    total: 0,
    isFetching: false,
    isComplete: false,
    progressMessage: '',
    error: null,
  },
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
      const listKey = tabToListKey(state.activeTab);
      state[listKey].isFetching = true;
      state[listKey].error = null;
    },
    fetchReportsSuccess: (state, action: PayloadAction<{ tab: TabType; data: ReportItem[] }>) => {
      const listKey = tabToListKey(action.payload.tab);
      state[listKey].isFetching = false;
      state[listKey].data = action.payload.data;
    },
    fetchReportsFailure: (state, action: PayloadAction<{ tab: TabType; error: string }>) => {
      const listKey = tabToListKey(action.payload.tab);
      state[listKey].isFetching = false;
      state[listKey].error = action.payload.error;
    },

    fetchHistoryRunRequest: (state, action: PayloadAction<string>) => {
      const runId = action.payload;
      if (
        state.historyRunState.runId === runId
        && (state.historyRunState.isFetching || state.historyRunState.data)
      ) {
        return;
      }
      state.historyRunState = {
        runId,
        data: null,
        isFetching: true,
        error: null,
      };
    },
    fetchHistoryRunSuccess: (state, action: PayloadAction<{ runId: string; data: ValidationHistoryDetail }>) => {
      state.historyRunState = {
        runId: action.payload.runId,
        data: action.payload.data,
        isFetching: false,
        error: null,
      };
    },
    fetchHistoryRunError: (state, action: PayloadAction<{ runId: string; error: string }>) => {
      state.historyRunState = {
        runId: action.payload.runId,
        data: null,
        isFetching: false,
        error: action.payload.error,
      };
    },

    fetchMismatchesRequest: (state, action: PayloadAction<string>) => {
      const runId = action.payload;
      if (
        state.mismatchesState.runId === runId
        && (state.mismatchesState.isFetching || state.mismatchesState.isComplete)
      ) {
        return;
      }
      state.mismatchesState = {
        runId,
        items: [],
        total: 0,
        isFetching: true,
        isComplete: false,
        progressMessage: 'Loading mismatch rows…',
        error: null,
      };
    },
    fetchMismatchesProgress: (state, action: PayloadAction<{
      runId: string;
      items: MismatchSampleRow[];
      total: number;
      progressMessage: string;
    }>) => {
      state.mismatchesState = {
        runId: action.payload.runId,
        items: action.payload.items,
        total: action.payload.total,
        isFetching: true,
        isComplete: false,
        progressMessage: action.payload.progressMessage,
        error: null,
      };
    },
    fetchMismatchesSuccess: (state, action: PayloadAction<{
      runId: string;
      items: MismatchSampleRow[];
      total: number;
    }>) => {
      state.mismatchesState = {
        runId: action.payload.runId,
        items: action.payload.items,
        total: action.payload.total,
        isFetching: false,
        isComplete: true,
        progressMessage: '',
        error: null,
      };
    },
    fetchMismatchesError: (state, action: PayloadAction<{ runId: string; error: string }>) => {
      state.mismatchesState = {
        runId: action.payload.runId,
        items: [],
        total: 0,
        isFetching: false,
        isComplete: true,
        progressMessage: '',
        error: action.payload.error,
      };
    },
  },
});

export const reportActions = reportSlice.actions;
export const reportReducer = reportSlice.reducer;
