import { all, call, put, takeLatest } from 'redux-saga/effects'
import { AxiosError, AxiosHeaders } from 'axios'
import { afterEach, vi } from 'vitest'

import {
  mockActiveReport,
  mockCompletedReport,
  mockHistoryRunDetail,
  mockMismatchRow,
  mockSavedReport,
} from '../Report.mockData'
import { reportActions } from '../Report.reducer'
import {
  fetchHistoryRunSaga,
  fetchMismatchesSaga,
  handleFetchReports,
  reportSaga,
} from '../Report.saga'
import { ReportService } from '../Report.service'

vi.mock('../Report.service', () => ({
  ReportService: {
    fetchActive: vi.fn(),
    fetchCompleted: vi.fn(),
    fetchSaved: vi.fn(),
    fetchHistoryRun: vi.fn(),
    fetchMismatchesPage: vi.fn(),
  },
}))

vi.mock('antd', () => ({
  notification: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('Report sagas', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('handleFetchReports', () => {
    it('fetches active reports when Active tab is selected', () => {
      const iterator = handleFetchReports() as Generator<unknown, void, unknown>
      iterator.next()
      expect(iterator.next('Active').value).toEqual(call(ReportService.fetchActive))
      expect(iterator.next([mockActiveReport]).value).toEqual(
        put(reportActions.fetchReportsSuccess({ tab: 'Active', data: [mockActiveReport] })),
      )
    })

    it('fetches completed reports when Completed tab is selected', () => {
      const iterator = handleFetchReports() as Generator<unknown, void, unknown>
      iterator.next()
      expect(iterator.next('Completed').value).toEqual(call(ReportService.fetchCompleted))
      expect(iterator.next([mockCompletedReport]).value).toEqual(
        put(reportActions.fetchReportsSuccess({ tab: 'Completed', data: [mockCompletedReport] })),
      )
    })

    it('fetches saved reports when Saved tab is selected', () => {
      const iterator = handleFetchReports() as Generator<unknown, void, unknown>
      iterator.next()
      expect(iterator.next('Saved').value).toEqual(call(ReportService.fetchSaved))
      expect(iterator.next([mockSavedReport]).value).toEqual(
        put(reportActions.fetchReportsSuccess({ tab: 'Saved', data: [mockSavedReport] })),
      )
    })

    it('dispatches failure when fetch throws', () => {
      const iterator = handleFetchReports() as Generator<unknown, void, unknown>
      iterator.next()
      iterator.next('Active')
      const error = new Error('Network error')
      expect(iterator.throw(error).value).toEqual(
        put(reportActions.fetchReportsFailure({ tab: 'Active', error: 'Network error' })),
      )
    })
  })

  describe('fetchHistoryRunSaga', () => {
    it('dispatches success when history run is fetched', () => {
      const action = { type: reportActions.fetchHistoryRunRequest.type, payload: 'run-completed-1' }
      const iterator = fetchHistoryRunSaga(action) as Generator<unknown, void, unknown>
      iterator.next()
      expect(iterator.next({
        runId: null,
        data: null,
        isFetching: false,
        error: null,
      }).value).toEqual(call(ReportService.fetchHistoryRun, 'run-completed-1'))
      expect(iterator.next(mockHistoryRunDetail).value).toEqual(
        put(reportActions.fetchHistoryRunSuccess({ runId: 'run-completed-1', data: mockHistoryRunDetail })),
      )
    })

    it('dispatches error when history run fetch fails', () => {
      const action = { type: reportActions.fetchHistoryRunRequest.type, payload: 'run-completed-1' }
      const iterator = fetchHistoryRunSaga(action) as Generator<unknown, void, unknown>
      iterator.next()
      iterator.next({
        runId: null,
        data: null,
        isFetching: false,
        error: null,
      })
      const error = new Error('Load failed')
      expect(iterator.throw(error).value).toEqual(
        put(reportActions.fetchHistoryRunError({ runId: 'run-completed-1', error: 'Load failed' })),
      )
    })
  })

  describe('fetchMismatchesSaga', () => {
    it('dispatches success when mismatch page is returned', () => {
      const action = { type: reportActions.fetchMismatchesRequest.type, payload: 'run-completed-1' }
      const iterator = fetchMismatchesSaga(action) as Generator<unknown, void, unknown>
      iterator.next()
      expect(iterator.next({
        runId: null,
        items: [],
        total: 0,
        isFetching: false,
        isComplete: false,
        progressMessage: '',
        error: null,
      }).value).toEqual(
        call(ReportService.fetchMismatchesPage, 'run-completed-1', { limit: 5000, offset: 0 }),
      )
      expect(
        iterator.next({
          run_id: 'run-completed-1',
          items: [mockMismatchRow],
          total: 1,
          offset: 0,
          limit: 5000,
        }).value,
      ).toEqual(
        put(
          reportActions.fetchMismatchesSuccess({
            runId: 'run-completed-1',
            items: [mockMismatchRow],
            total: 1,
          }),
        ),
      )
    })

    it('skips fetch when mismatches are already loaded for the run', () => {
      const action = { type: reportActions.fetchMismatchesRequest.type, payload: 'run-completed-1' }
      const iterator = fetchMismatchesSaga(action) as Generator<unknown, void, unknown>
      iterator.next()
      expect(
        iterator.next({
          runId: 'run-completed-1',
          items: [mockMismatchRow],
          total: 1,
          isFetching: false,
          isComplete: true,
          progressMessage: '',
          error: null,
        }).done,
      ).toBe(true)
    })

    it('dispatches error when mismatch fetch fails', () => {
      const action = { type: reportActions.fetchMismatchesRequest.type, payload: 'run-completed-1' }
      const iterator = fetchMismatchesSaga(action) as Generator<unknown, void, unknown>
      iterator.next()
      iterator.next({
        runId: null,
        items: [],
        total: 0,
        isFetching: false,
        isComplete: false,
        progressMessage: '',
        error: null,
      })
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
          data: { message: 'Failed to load mismatch rows' },
        },
      )
      expect(iterator.throw(axiosError).value).toEqual(
        put(reportActions.fetchMismatchesError({ runId: 'run-completed-1', error: 'Failed to load mismatch rows' })),
      )
    })
  })

  describe('reportSaga root watcher', () => {
    it('registers takeLatest watchers for report actions', () => {
      const iterator = reportSaga()
      expect(iterator.next().value).toEqual(
        all([
          takeLatest(reportActions.fetchReportsRequest.type, handleFetchReports),
          takeLatest(reportActions.setTab.type, handleFetchReports),
          takeLatest(reportActions.fetchHistoryRunRequest.type, fetchHistoryRunSaga),
          takeLatest(reportActions.fetchMismatchesRequest.type, fetchMismatchesSaga),
        ]),
      )
      expect(iterator.next().done).toBe(true)
    })
  })
})
