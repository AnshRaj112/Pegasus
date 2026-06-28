import { all, call, put, takeLatest } from 'redux-saga/effects'
import { AxiosError, AxiosHeaders } from 'axios'
import { afterEach, vi } from 'vitest'

import { mockUserProfile } from '../Profile.mockData'
import { profileActions } from '../Profile.reducer'
import { fetchProfileSaga, profileSaga } from '../Profile.saga'
import { fetchUserProfile } from '../Profile.service'

vi.mock('../Profile.service', () => ({
  fetchUserProfile: vi.fn(),
}))

vi.mock('antd', () => ({
  notification: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('Profile sagas', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchProfileSaga', () => {
    it('dispatches success when profile is fetched', () => {
      const iterator = fetchProfileSaga()
      expect(iterator.next().value).toEqual(call(fetchUserProfile))
      expect(iterator.next(mockUserProfile).value).toEqual(
        put(profileActions.fetchProfileSuccess(mockUserProfile)),
      )
      expect(iterator.next().done).toBe(true)
    })

    it('dispatches error when fetch fails', () => {
      const iterator = fetchProfileSaga()
      iterator.next()
      const error = new Error('Network error')
      expect(iterator.throw(error).value).toEqual(
        put(profileActions.fetchProfileError('Network error')),
      )
    })

    it('dispatches error with API message when fetch fails with AxiosError', () => {
      const iterator = fetchProfileSaga()
      iterator.next()
      const axiosError = new AxiosError(
        'Server error',
        'ERR_BAD_REQUEST',
        undefined,
        undefined,
        {
          status: 500,
          statusText: 'Internal Server Error',
          headers: {},
          config: { headers: new AxiosHeaders() },
          data: { message: 'Failed to fetch profile' },
        },
      )
      expect(iterator.throw(axiosError).value).toEqual(
        put(profileActions.fetchProfileError('Failed to fetch profile')),
      )
    })
  })

  describe('profileSaga root watcher', () => {
    it('registers takeLatest for fetchProfileRequest', () => {
      const iterator = profileSaga()
      expect(iterator.next().value).toEqual(
        all([takeLatest(profileActions.fetchProfileRequest.type, fetchProfileSaga)]),
      )
      expect(iterator.next().done).toBe(true)
    })
  })
})
