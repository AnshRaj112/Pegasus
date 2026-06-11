import { type PayloadAction, createSlice } from '@reduxjs/toolkit';
import { type AuthReducerState } from './Auth.interface';

export const initialState: AuthReducerState = {
  isAuthenticated: false,
  user: null,
  isLoading: false,
  error: null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    loginRequest: (state, _action: PayloadAction<{ email: string; password: string }>) => ({
      ...state,
      isLoading: true,
      error: null,
    }),
    loginSuccess: (state, action: PayloadAction<{ email: string; fullName: string }>) => ({
      ...state,
      isLoading: false,
      isAuthenticated: true,
      user: action.payload,
    }),
    loginFailure: (state, action: PayloadAction<string>) => ({
      ...state,
      isLoading: false,
      error: action.payload,
    }),
  },
});

export const authActions = { ...authSlice.actions };
export default authSlice.reducer;