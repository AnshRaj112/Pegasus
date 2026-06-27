import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import { AuthReducerState } from './Auth.interface';

export const initialState: AuthReducerState = {
  isAuthenticated: false,
  user: null,
  isFetching: true,
  error: null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    loginRequest: (state, _action: PayloadAction<{ email: string; password: string }>) => ({
      ...state,
      isFetching: true,
      error: null,
    }),
    loginSuccess: (state, action: PayloadAction<{ email: string; fullName: string }>) => ({
      ...state,
      isFetching: false,
      isAuthenticated: true,
      user: action.payload,
    }),
    loginFailure: (state, action: PayloadAction<string>) => ({
      ...state,
      isFetching: false,
      error: action.payload,
    }),
    logoutSuccess: (state) => ({
      ...state,
      isFetching: false,
      isAuthenticated: false,
      user: null,
      error: null,
    }),
    setSession: (state, action: PayloadAction<{ email: string } | null>) => ({
      ...state,
      isFetching: false,
      isAuthenticated: Boolean(action.payload),
      user: action.payload ? { email: action.payload.email, fullName: action.payload.email } : null,
      error: null,
    }),
  },
});

export const authActions = { ...authSlice.actions };
export default authSlice.reducer;