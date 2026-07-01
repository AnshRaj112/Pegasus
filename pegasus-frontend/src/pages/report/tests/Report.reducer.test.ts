import { reportActions, reportReducer, initialState, mergeActiveReportItems } from '../Report.reducer'
import {
  activeReportsError,
  activeReportsLoading,
  activeReportsSuccess,
  completedReportsSuccess,
  historyRunLoading,
  historyRunSuccess,
  mismatchesLoading,
  mismatchesSuccess,
  mockActiveReport,
  mockCompletedReport,
  mockHistoryRunDetail,
  mockMismatchRow,
  mockSavedReport,
  savedReportsSuccess,
} from '../Report.mockData'

describe('Report reducer', () => {
  it('returns initial state for unknown action', () => {
    expect(reportReducer(undefined, { type: 'unknown' })).toEqual(initialState)
  })

  describe('tab and search', () => {
    it('sets active tab on setTab', () => {
      expect(reportReducer(initialState, reportActions.setTab('Completed')).activeTab).toBe('Completed')
    })

    it('updates search query on setSearchQuery', () => {
      expect(reportReducer(initialState, reportActions.setSearchQuery('acme')).searchQuery).toBe('acme')
    })
  })

  describe('fetchReports', () => {
    it('sets loading on active tab fetchReportsRequest when list is empty', () => {
      const result = reportReducer(initialState, reportActions.fetchReportsRequest())
      expect(result.activeReports).toEqual(activeReportsLoading)
    })

    it('keeps active reports visible while refreshing when list already has data', () => {
      const state = { ...initialState, activeReports: activeReportsSuccess }
      const result = reportReducer(state, reportActions.fetchReportsRequest())
      expect(result.activeReports.isFetching).toBe(false)
      expect(result.activeReports.data).toEqual(activeReportsSuccess.data)
    })

    it('shows an optimistic active row on showActiveValidation', () => {
      const result = reportReducer(initialState, reportActions.showActiveValidation(mockActiveReport))
      expect(result.activeTab).toBe('Active')
      expect(result.activeReports.data).toEqual([mockActiveReport])
      expect(result.activeReports.isFetching).toBe(false)
    })

    it('stores active reports on fetchReportsSuccess', () => {
      expect(
        reportReducer(initialState, reportActions.fetchReportsSuccess({ tab: 'Active', data: [mockActiveReport] })),
      ).toEqual({
        ...initialState,
        activeReports: activeReportsSuccess,
      })
    })

    it('stores completed reports on fetchReportsSuccess for Completed tab', () => {
      const state = { ...initialState, activeTab: 'Completed' as const }
      expect(
        reportReducer(state, reportActions.fetchReportsSuccess({ tab: 'Completed', data: [mockCompletedReport] })),
      ).toEqual({
        ...state,
        completedReports: completedReportsSuccess,
      })
    })

    it('stores saved reports on fetchReportsSuccess for Saved tab', () => {
      const state = { ...initialState, activeTab: 'Saved' as const }
      expect(
        reportReducer(state, reportActions.fetchReportsSuccess({ tab: 'Saved', data: [mockSavedReport] })),
      ).toEqual({
        ...state,
        savedReports: savedReportsSuccess,
      })
    })

    it('stores error on fetchReportsFailure for active tab', () => {
      expect(
        reportReducer(initialState, reportActions.fetchReportsFailure({ tab: 'Active', error: 'Failed to fetch reports' })),
      ).toEqual({
        ...initialState,
        activeReports: activeReportsError,
      })
    })
    it('merges refreshed active rows without losing known file names', () => {
      const state = { ...initialState, activeReports: activeReportsSuccess }
      const refreshed = [{
        ...mockActiveReport,
        sourceTitle: '—',
        jobTitle: '—',
      }]
      const result = reportReducer(
        state,
        reportActions.fetchReportsSuccess({ tab: 'Active', data: refreshed }),
      )
      expect(result.activeReports.data[0].sourceTitle).toBe('source.csv')
      expect(result.activeReports.data[0].jobTitle).toBe('target.csv')
    })
  })

  describe('mergeActiveReportItems', () => {
    it('keeps existing titles when incoming rows are blank', () => {
      const merged = mergeActiveReportItems(
        [mockActiveReport],
        [{ ...mockActiveReport, sourceTitle: '—', jobTitle: '—' }],
      )
      expect(merged[0].sourceTitle).toBe('source.csv')
      expect(merged[0].jobTitle).toBe('target.csv')
    })
  })

  describe('fetchHistoryRun', () => {
    it('sets loading on fetchHistoryRunRequest', () => {
      expect(reportReducer(initialState, reportActions.fetchHistoryRunRequest('run-completed-1')).historyRunState).toEqual(
        historyRunLoading,
      )
    })

    it('stores data on fetchHistoryRunSuccess', () => {
      expect(
        reportReducer(
          initialState,
          reportActions.fetchHistoryRunSuccess({ runId: 'run-completed-1', data: mockHistoryRunDetail }),
        ).historyRunState,
      ).toEqual(historyRunSuccess)
    })

    it('stores error on fetchHistoryRunError', () => {
      const result = reportReducer(
        initialState,
        reportActions.fetchHistoryRunError({ runId: 'run-completed-1', error: 'Failed to load validation run' }),
      )
      expect(result.historyRunState.error).toBe('Failed to load validation run')
      expect(result.historyRunState.isFetching).toBe(false)
    })
  })

  describe('fetchMismatches', () => {
    it('sets loading on fetchMismatchesRequest', () => {
      expect(
        reportReducer(initialState, reportActions.fetchMismatchesRequest('run-completed-1')).mismatchesState,
      ).toEqual(mismatchesLoading)
    })

    it('updates progress on fetchMismatchesProgress', () => {
      const result = reportReducer(
        initialState,
        reportActions.fetchMismatchesProgress({
          runId: 'run-completed-1',
          items: [mockMismatchRow],
          total: 1,
          progressMessage: 'Loaded 1 / 1 mismatch rows…',
        }),
      )
      expect(result.mismatchesState.items).toEqual([mockMismatchRow])
      expect(result.mismatchesState.isFetching).toBe(true)
      expect(result.mismatchesState.progressMessage).toContain('Loaded 1')
    })

    it('stores data on fetchMismatchesSuccess', () => {
      expect(
        reportReducer(
          initialState,
          reportActions.fetchMismatchesSuccess({
            runId: 'run-completed-1',
            items: [mockMismatchRow],
            total: 1,
          }),
        ).mismatchesState,
      ).toEqual(mismatchesSuccess)
    })

    it('stores error on fetchMismatchesError', () => {
      const result = reportReducer(
        initialState,
        reportActions.fetchMismatchesError({ runId: 'run-completed-1', error: 'Failed to load mismatch rows' }),
      )
      expect(result.mismatchesState.error).toBe('Failed to load mismatch rows')
      expect(result.mismatchesState.isComplete).toBe(true)
    })
  })
})
