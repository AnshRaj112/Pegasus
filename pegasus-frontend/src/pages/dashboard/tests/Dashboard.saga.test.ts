import { all, call, put, takeLatest } from 'redux-saga/effects'
import { AxiosError, AxiosHeaders } from 'axios'
import { afterEach, vi } from 'vitest'

import { mockCreateEntityPayload, mockDashboardData } from '../Dashboard.mockData'
import { dashboardActions } from '../Dashboard.reducer'
import { createEntitySaga, dashboardSaga, fetchDashboardDataSaga } from '../Dashboard.saga'
import { DashboardServiceApi } from '../Dashboard.service'

vi.mock('../Dashboard.service', () => ({
  DashboardServiceApi: {
    fetchDashboardData: vi.fn(),
    createEntity: vi.fn(),
  },
}))

vi.mock('antd', () => ({
  notification: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const createAxiosResponse = <T,>(data: T) => ({
  data,
  status: 200,
  statusText: 'OK',
  headers: {},
  config: { headers: new AxiosHeaders() },
})

describe('Dashboard sagas', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('fetchDashboardDataSaga', () => {
    it('dispatches success when dashboard data is fetched', () => {
      const iterator = fetchDashboardDataSaga()
      expect(iterator.next().value).toEqual(call(DashboardServiceApi.fetchDashboardData))
      expect(iterator.next(createAxiosResponse(mockDashboardData)).value).toEqual(
        put(dashboardActions.fetchDashboardDataSuccess(mockDashboardData)),
      )
      expect(iterator.next().done).toBe(true)
    })

    it('dispatches error when fetch fails', () => {
      const iterator = fetchDashboardDataSaga()
      iterator.next()
      const error = new Error('Network error')
      expect(iterator.throw(error).value).toEqual(
        put(dashboardActions.fetchDashboardDataError('Network error')),
      )
    })

    it('dispatches error with API message when fetch fails with AxiosError', () => {
      const iterator = fetchDashboardDataSaga()
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
          data: { message: 'Failed to fetch dashboard data' },
        },
      )
      expect(iterator.throw(axiosError).value).toEqual(
        put(dashboardActions.fetchDashboardDataError('Failed to fetch dashboard data')),
      )
    })
  })

  describe('createEntitySaga', () => {
    it('dispatches success and refetches dashboard data on create', () => {
      const action = { type: dashboardActions.createEntityRequest.type, payload: mockCreateEntityPayload }
      const iterator = createEntitySaga(action)
      expect(iterator.next().value).toEqual(
        call(DashboardServiceApi.createEntity, mockCreateEntityPayload),
      )
      expect(iterator.next().value).toEqual(
        put(dashboardActions.createEntitySuccess('Entity "New Entity" saved')),
      )
      expect(iterator.next().value).toEqual(put(dashboardActions.fetchDashboardDataRequest()))
      expect(iterator.next().done).toBe(true)
    })

    it('dispatches error when create fails', () => {
      const action = { type: dashboardActions.createEntityRequest.type, payload: mockCreateEntityPayload }
      const iterator = createEntitySaga(action)
      iterator.next()
      const error = new Error('Create failed')
      expect(iterator.throw(error).value).toEqual(
        put(dashboardActions.createEntityError('Create failed')),
      )
    })
  })

  describe('dashboardSaga root watcher', () => {
    it('registers takeLatest watchers for fetch and create actions', () => {
      const iterator = dashboardSaga()
      expect(iterator.next().value).toEqual(
        all([
          takeLatest(dashboardActions.fetchDashboardDataRequest.type, fetchDashboardDataSaga),
          takeLatest(dashboardActions.createEntityRequest.type, createEntitySaga),
        ]),
      )
      expect(iterator.next().done).toBe(true)
    })
  })
})
