import authReducer, { authActions, initialState } from '../Auth.reducer'
import {
  authenticatedState,
  loginErrorState,
  loginLoadingState,
  loggedOutState,
  mockLoginCredentials,
  mockSessionUser,
  mockUser,
  sessionFromEmailState,
} from '../Auth.mockData'

describe('Auth reducer', () => {
  it('returns initial state for unknown action', () => {
    expect(authReducer(undefined, { type: 'unknown' })).toEqual(initialState)
  })

  describe('login', () => {
    it('sets loading on loginRequest', () => {
      expect(authReducer(initialState, authActions.loginRequest(mockLoginCredentials))).toEqual(loginLoadingState)
    })

    it('stores user on loginSuccess', () => {
      expect(authReducer(initialState, authActions.loginSuccess(mockUser))).toEqual(authenticatedState)
    })

    it('stores error on loginFailure', () => {
      expect(authReducer(initialState, authActions.loginFailure('Invalid credentials'))).toEqual(loginErrorState)
    })
  })

  describe('logout', () => {
    it('clears session on logoutSuccess', () => {
      expect(authReducer(authenticatedState, authActions.logoutSuccess())).toEqual(loggedOutState)
    })
  })

  describe('setSession', () => {
    it('sets authenticated user from email payload', () => {
      expect(authReducer(initialState, authActions.setSession(mockSessionUser))).toEqual(sessionFromEmailState)
    })

    it('clears session when payload is null', () => {
      expect(authReducer(authenticatedState, authActions.setSession(null))).toEqual(loggedOutState)
    })
  })
})
