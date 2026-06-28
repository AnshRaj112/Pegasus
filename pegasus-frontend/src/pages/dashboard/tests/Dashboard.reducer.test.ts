import dashboardReducer, { dashboardActions, initialState } from '../Dashboard.reducer'
import {
  createEntityError,
  createEntityLoading,
  createEntitySuccess,
  dashboardDataError,
  dashboardDataLoading,
  dashboardDataSuccess,
  mockCreateEntityPayload,
  mockDashboardData,
} from '../Dashboard.mockData'

describe('Dashboard reducer', () => {
  it('returns initial state for unknown action', () => {
    expect(dashboardReducer(undefined, { type: 'unknown' })).toEqual(initialState)
  })

  describe('fetchDashboardData', () => {
    it('sets loading on fetchDashboardDataRequest', () => {
      expect(dashboardReducer(initialState, dashboardActions.fetchDashboardDataRequest())).toEqual(dashboardDataLoading)
    })

    it('stores data on fetchDashboardDataSuccess', () => {
      expect(dashboardReducer(initialState, dashboardActions.fetchDashboardDataSuccess(mockDashboardData))).toEqual(
        dashboardDataSuccess,
      )
    })

    it('stores error on fetchDashboardDataError', () => {
      expect(
        dashboardReducer(initialState, dashboardActions.fetchDashboardDataError('Failed to fetch dashboard data')),
      ).toEqual(dashboardDataError)
    })
  })

  describe('createEntity', () => {
    it('sets loading on createEntityRequest', () => {
      expect(
        dashboardReducer(dashboardDataSuccess, dashboardActions.createEntityRequest(mockCreateEntityPayload)),
      ).toEqual(createEntityLoading)
    })

    it('stores success message on createEntitySuccess', () => {
      expect(
        dashboardReducer(dashboardDataSuccess, dashboardActions.createEntitySuccess('Entity "New Entity" saved')),
      ).toEqual(createEntitySuccess)
    })

    it('stores error on createEntityError', () => {
      expect(
        dashboardReducer(
          dashboardDataSuccess,
          dashboardActions.createEntityError('Could not save entity (persistence may be disabled)'),
        ),
      ).toEqual(createEntityError)
    })
  })
})
