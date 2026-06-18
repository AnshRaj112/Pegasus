import { type PayloadAction, createSlice } from '@reduxjs/toolkit';
import { type AuthReducerState } from './Auth.interface';

export const initialState: AuthReducerState = {
  isAuthenticated: false,
  user: null,
  isLoading: true,
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
    logoutSuccess: (state) => ({
      ...state,
      isLoading: false,
      isAuthenticated: false,
      user: null,
      error: null,
    }),
    setSession: (state, action: PayloadAction<{ email: string } | null>) => ({
      ...state,
      isLoading: false,
      isAuthenticated: Boolean(action.payload),
      user: action.payload ? { email: action.payload.email, fullName: action.payload.email } : null,
      error: null,
    }),
  },
});

export const authActions = { ...authSlice.actions };
export default authSlice.reducer;