import { initializeNullState } from '~/shared/constants/common.constants'

import { AuthReducerState } from './Auth.interface'
import { initialState } from './Auth.reducer'

export const mockUser = {
  email: 'admin@pegasus.io',
  fullName: 'Admin User',
}

export const mockSessionUser = {
  email: 'admin@pegasus.io',
}

export const mockLoginCredentials = {
  email: 'admin@pegasus.io',
  password: 'secret-password',
}

export const authenticatedState: AuthReducerState = {
  isAuthenticated: true,
  user: mockUser,
  isFetching: false,
  error: null,
}

export const loginLoadingState: AuthReducerState = {
  ...initialState,
  isFetching: true,
  error: null,
}

export const loginErrorState: AuthReducerState = {
  ...initialState,
  isFetching: false,
  error: 'Invalid credentials',
}

export const loggedOutState: AuthReducerState = {
  isAuthenticated: false,
  user: null,
  isFetching: false,
  error: null,
}

export const sessionBootstrappingState: AuthReducerState = {
  ...initialState,
  isFetching: true,
}

export const sessionFromEmailState: AuthReducerState = {
  isAuthenticated: true,
  user: {
    email: mockSessionUser.email,
    fullName: mockSessionUser.email,
  },
  isFetching: false,
  error: null,
}

export const authFetchState = {
  ...initializeNullState,
}
