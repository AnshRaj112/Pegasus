import profileReducer, { initialState, profileActions } from '../Profile.reducer'
import {
  fetchProfileError,
  fetchProfileLoading,
  fetchProfileSuccess,
  mockUserProfile,
} from '../Profile.mockData'

describe('Profile reducer', () => {
  it('returns initial state for unknown action', () => {
    expect(profileReducer(undefined, { type: 'unknown' })).toEqual(initialState)
  })

  describe('fetchProfile', () => {
    it('sets loading on fetchProfileRequest', () => {
      expect(profileReducer(initialState, profileActions.fetchProfileRequest())).toEqual(fetchProfileLoading)
    })

    it('stores data on fetchProfileSuccess', () => {
      expect(profileReducer(initialState, profileActions.fetchProfileSuccess(mockUserProfile))).toEqual(
        fetchProfileSuccess,
      )
    })

    it('stores error on fetchProfileError', () => {
      expect(profileReducer(initialState, profileActions.fetchProfileError('Failed to fetch profile'))).toEqual(
        fetchProfileError,
      )
    })
  })
})
