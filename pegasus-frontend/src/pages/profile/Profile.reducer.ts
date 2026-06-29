import { PayloadAction, createSlice } from '@reduxjs/toolkit';

import { initializeNullState } from '~/shared/constants/common.constants';

import { ProfileReducerState, UserProfile } from './Profile.interface';

export const initialState: ProfileReducerState = {
  fetchProfileState: initializeNullState,
};

const profileSlice = createSlice({
  name: 'profile',
  initialState,
  reducers: {
    fetchProfileRequest: (state) => ({
      ...state,
      fetchProfileState: {
        ...initializeNullState,
        isFetching: true,
      },
    }),
    fetchProfileSuccess: (state, action: PayloadAction<UserProfile>) => ({
      ...state,
      fetchProfileState: {
        ...initializeNullState,
        data: action.payload,
      },
    }),
    fetchProfileError: (state, action: PayloadAction<string>) => ({
      ...state,
      fetchProfileState: {
        ...initializeNullState,
        error: action.payload,
      },
    }),
  },
});

export const profileActions = {
  ...profileSlice.actions,
};

export default profileSlice.reducer;
