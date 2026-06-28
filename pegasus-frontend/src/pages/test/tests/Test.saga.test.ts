import { all, delay, put, takeLatest } from 'redux-saga/effects'
import { AxiosError, AxiosHeaders } from 'axios'
import { afterEach, vi } from 'vitest'

import { mockActiveTests, mockCompletedTests, mockSavedTests } from '../Test.mockdata'
import { testActions } from '../Test.reducer'
import {
  fetchActiveTestsSaga,
  fetchCompletedTestsSaga,
  fetchSavedTestsSaga,
  testSaga,
} from '../Test.saga'

vi.mock('antd', () => ({
  notification: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('Test sagas', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchActiveTestsSaga', () => {
    it('dispatches success after delay with mock active tests', () => {
      const iterator = fetchActiveTestsSaga()
      expect(iterator.next().value).toEqual(delay(800))
      expect(iterator.next().value).toEqual(put(testActions.fetchActiveTestsSuccess(mockActiveTests)))
      expect(iterator.next().done).toBe(true)
    })

    it('dispatches error when an AxiosError is thrown', () => {
      const iterator = fetchActiveTestsSaga()
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
          data: { message: 'Failed to load active tests.' },
        },
      )
      expect(iterator.throw(axiosError).value).toEqual(
        put(testActions.fetchActiveTestsError('Failed to load active tests.')),
      )
    })
  })

  describe('fetchCompletedTestsSaga', () => {
    it('dispatches success after delay with mock completed tests', () => {
      const iterator = fetchCompletedTestsSaga()
      expect(iterator.next().value).toEqual(delay(800))
      expect(iterator.next().value).toEqual(put(testActions.fetchCompletedTestsSuccess(mockCompletedTests)))
    })

    it('dispatches error when an AxiosError is thrown', () => {
      const iterator = fetchCompletedTestsSaga()
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
          data: { message: 'Failed to load completed tests.' },
        },
      )
      expect(iterator.throw(axiosError).value).toEqual(
        put(testActions.fetchCompletedTestsError('Failed to load completed tests.')),
      )
    })
  })

  describe('fetchSavedTestsSaga', () => {
    it('dispatches success after delay with mock saved tests', () => {
      const iterator = fetchSavedTestsSaga()
      expect(iterator.next().value).toEqual(delay(800))
      expect(iterator.next().value).toEqual(put(testActions.fetchSavedTestsSuccess(mockSavedTests)))
    })

    it('dispatches error when an AxiosError is thrown', () => {
      const iterator = fetchSavedTestsSaga()
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
          data: { message: 'Failed to load saved tests.' },
        },
      )
      expect(iterator.throw(axiosError).value).toEqual(
        put(testActions.fetchSavedTestsError('Failed to load saved tests.')),
      )
    })
  })

  describe('testSaga root watcher', () => {
    it('registers takeLatest watchers for all test fetch actions', () => {
      const iterator = testSaga()
      expect(iterator.next().value).toEqual(
        all([
          takeLatest(testActions.fetchActiveTestsRequest.type, fetchActiveTestsSaga),
          takeLatest(testActions.fetchCompletedTestsRequest.type, fetchCompletedTestsSaga),
          takeLatest(testActions.fetchSavedTestsRequest.type, fetchSavedTestsSaga),
        ]),
      )
      expect(iterator.next().done).toBe(true)
    })
  })
})
