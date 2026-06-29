import testReducer, { initialState, testActions } from '../Test.reducer'
import {
  activeTestsError,
  activeTestsLoading,
  activeTestsSuccess,
  completedTestsSuccess,
  mockActiveTests,
  mockCompletedTests,
  mockSavedTests,
  savedTestsSuccess,
} from '../Test.mockdata'

describe('Test reducer', () => {
  it('returns initial state for unknown action', () => {
    expect(testReducer(undefined, { type: 'unknown' })).toEqual(initialState)
  })

  describe('activeTests', () => {
    it('sets loading on fetchActiveTestsRequest', () => {
      expect(testReducer(initialState, testActions.fetchActiveTestsRequest())).toEqual({
        ...initialState,
        activeTests: activeTestsLoading,
      })
    })

    it('stores data on fetchActiveTestsSuccess', () => {
      expect(testReducer(initialState, testActions.fetchActiveTestsSuccess(mockActiveTests))).toEqual({
        ...initialState,
        activeTests: activeTestsSuccess,
      })
    })

    it('stores error on fetchActiveTestsError', () => {
      expect(testReducer(initialState, testActions.fetchActiveTestsError('Failed to load active tests.'))).toEqual({
        ...initialState,
        activeTests: activeTestsError,
      })
    })
  })

  describe('completedTests', () => {
    it('sets loading on fetchCompletedTestsRequest', () => {
      const result = testReducer(initialState, testActions.fetchCompletedTestsRequest())
      expect(result.completedTests.isFetching).toBe(true)
      expect(result.completedTests.error).toBeNull()
    })

    it('stores data on fetchCompletedTestsSuccess', () => {
      expect(testReducer(initialState, testActions.fetchCompletedTestsSuccess(mockCompletedTests))).toEqual({
        ...initialState,
        completedTests: completedTestsSuccess,
      })
    })

    it('stores error on fetchCompletedTestsError', () => {
      const result = testReducer(initialState, testActions.fetchCompletedTestsError('Completed fetch failed'))
      expect(result.completedTests.error).toBe('Completed fetch failed')
      expect(result.completedTests.isFetching).toBe(false)
    })
  })

  describe('savedTests', () => {
    it('sets loading on fetchSavedTestsRequest', () => {
      const result = testReducer(initialState, testActions.fetchSavedTestsRequest())
      expect(result.savedTests.isFetching).toBe(true)
      expect(result.savedTests.error).toBeNull()
    })

    it('stores data on fetchSavedTestsSuccess', () => {
      expect(testReducer(initialState, testActions.fetchSavedTestsSuccess(mockSavedTests))).toEqual({
        ...initialState,
        savedTests: savedTestsSuccess,
      })
    })

    it('stores error on fetchSavedTestsError', () => {
      const result = testReducer(initialState, testActions.fetchSavedTestsError('Saved fetch failed'))
      expect(result.savedTests.error).toBe('Saved fetch failed')
      expect(result.savedTests.isFetching).toBe(false)
    })
  })
})
