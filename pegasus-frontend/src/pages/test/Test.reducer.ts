import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { initializeEmptyState } from '~/shared/constants/common.constants';
import { TestReducerState, TestEntity } from './Test.interface';

export const initialState: TestReducerState = {
  activeTests: initializeEmptyState,
  completedTests: initializeEmptyState,
  savedTests: initializeEmptyState,
};

const testSlice = createSlice({
  name: 'test',
  initialState,
  reducers: {
    // Active Tests
    fetchActiveTestsRequest: (state) => {
      state.activeTests.isFetching = true;
      state.activeTests.error = null;
    },
    fetchActiveTestsSuccess: (state, action: PayloadAction<TestEntity[]>) => {
      state.activeTests.isFetching = false;
      state.activeTests.data = action.payload;
    },
    fetchActiveTestsError: (state, action: PayloadAction<string>) => {
      state.activeTests.isFetching = false;
      state.activeTests.error = action.payload;
    },

    // Completed Tests
    fetchCompletedTestsRequest: (state) => {
      state.completedTests.isFetching = true;
      state.completedTests.error = null;
    },
    fetchCompletedTestsSuccess: (state, action: PayloadAction<TestEntity[]>) => {
      state.completedTests.isFetching = false;
      state.completedTests.data = action.payload;
    },
    fetchCompletedTestsError: (state, action: PayloadAction<string>) => {
      state.completedTests.isFetching = false;
      state.completedTests.error = action.payload;
    },

    // Saved Tests
    fetchSavedTestsRequest: (state) => {
      state.savedTests.isFetching = true;
      state.savedTests.error = null;
    },
    fetchSavedTestsSuccess: (state, action: PayloadAction<TestEntity[]>) => {
      state.savedTests.isFetching = false;
      state.savedTests.data = action.payload;
    },
    fetchSavedTestsError: (state, action: PayloadAction<string>) => {
      state.savedTests.isFetching = false;
      state.savedTests.error = action.payload;
    },
  },
});

export const testActions = { ...testSlice.actions };
export default testSlice.reducer;