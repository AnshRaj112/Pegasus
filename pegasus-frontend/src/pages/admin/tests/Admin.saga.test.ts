import { call, delay, put, takeLatest } from 'redux-saga/effects'
import { afterEach, vi } from 'vitest'

import {
  mockCreateProviderPayload,
  mockStorageProvider,
  mockUpdateProviderPayload,
  mockWorkspaceItems,
} from '../Admin.mockData'
import { adminActions, initialState } from '../Admin.reducer'
import adminSaga, {
  handleCreateProviderSaga,
  handleDeleteProviderSaga,
  handleFetchProvidersSaga,
  handleFetchWorkspacesSaga,
  handleTestConnectionSaga,
  handleUpdateProviderSaga,
} from '../Admin.saga'
import { adminService } from '../Admin.service'

vi.mock('../Admin.service', () => ({
  adminService: {
    fetchWorkspaces: vi.fn(),
    fetchStorageProviders: vi.fn(),
    createStorageProvider: vi.fn(),
    updateStorageProvider: vi.fn(),
    deleteStorageProvider: vi.fn(),
    testConnection: vi.fn(),
  },
}))

vi.mock('antd', () => ({
  notification: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('Admin sagas', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('handleFetchWorkspacesSaga', () => {
    it('dispatches success when workspaces are fetched', () => {
      const iterator = handleFetchWorkspacesSaga()
      expect(iterator.next().value).toEqual(call([adminService, adminService.fetchWorkspaces]))
      expect(iterator.next(mockWorkspaceItems).value).toEqual(
        put(adminActions.fetchWorkspacesSuccess(mockWorkspaceItems)),
      )
      expect(iterator.next().done).toBe(true)
    })

    it('dispatches error when fetch fails', () => {
      const iterator = handleFetchWorkspacesSaga()
      iterator.next()
      const error = new Error('Network error')
      expect(iterator.throw(error).value).toEqual(
        put(adminActions.fetchWorkspacesError('Network error')),
      )
    })
  })

  describe('handleFetchProvidersSaga', () => {
    it('dispatches success when providers are fetched', () => {
      const iterator = handleFetchProvidersSaga()
      expect(iterator.next().value).toEqual(call([adminService, adminService.fetchStorageProviders]))
      expect(iterator.next([mockStorageProvider]).value).toEqual(
        put(adminActions.fetchProvidersSuccess([mockStorageProvider])),
      )
    })

    it('dispatches error when fetch fails', () => {
      const iterator = handleFetchProvidersSaga()
      iterator.next()
      const error = new Error('Fetch failed')
      expect(iterator.throw(error).value).toEqual(
        put(adminActions.fetchProvidersError('Fetch failed')),
      )
    })
  })

  describe('handleCreateProviderSaga', () => {
    it('dispatches success and shows notification on create', () => {
      const action = { type: adminActions.createProviderRequest.type, payload: mockCreateProviderPayload }
      const iterator = handleCreateProviderSaga(action)
      expect(iterator.next().value).toEqual(
        call([adminService, adminService.createStorageProvider], mockCreateProviderPayload),
      )
      expect(iterator.next(mockStorageProvider).value).toEqual(
        put(adminActions.createProviderSuccess(mockStorageProvider)),
      )
    })

    it('dispatches error when create fails', () => {
      const action = { type: adminActions.createProviderRequest.type, payload: mockCreateProviderPayload }
      const iterator = handleCreateProviderSaga(action)
      iterator.next()
      const error = new Error('Create failed')
      expect(iterator.throw(error).value).toEqual(
        put(adminActions.createProviderError('Create failed')),
      )
    })
  })

  describe('handleUpdateProviderSaga', () => {
    it('dispatches success when provider is updated', () => {
      const action = { type: adminActions.updateProviderRequest.type, payload: mockUpdateProviderPayload }
      const updated = { ...mockStorageProvider, name: 'Updated Connection' }
      const iterator = handleUpdateProviderSaga(action)
      expect(iterator.next().value).toEqual(
        call([adminService, adminService.updateStorageProvider], mockUpdateProviderPayload),
      )
      expect(iterator.next(updated).value).toEqual(put(adminActions.updateProviderSuccess(updated)))
    })

    it('dispatches error when update fails', () => {
      const action = { type: adminActions.updateProviderRequest.type, payload: mockUpdateProviderPayload }
      const iterator = handleUpdateProviderSaga(action)
      iterator.next()
      const error = new Error('Update failed')
      expect(iterator.throw(error).value).toEqual(
        put(adminActions.updateProviderError('Update failed')),
      )
    })
  })

  describe('handleDeleteProviderSaga', () => {
    it('dispatches success when provider is deleted', () => {
      const action = { type: adminActions.deleteProviderRequest.type, payload: 'sp-1' }
      const iterator = handleDeleteProviderSaga(action)
      expect(iterator.next().value).toEqual(call([adminService, adminService.deleteStorageProvider], 'sp-1'))
      expect(iterator.next().value).toEqual(put(adminActions.deleteProviderSuccess('sp-1')))
    })

    it('dispatches error when delete fails', () => {
      const action = { type: adminActions.deleteProviderRequest.type, payload: 'sp-1' }
      const iterator = handleDeleteProviderSaga(action)
      iterator.next()
      const error = new Error('Delete failed')
      expect(iterator.throw(error).value).toEqual(
        put(adminActions.deleteProviderError('Delete failed')),
      )
    })
  })

  describe('handleTestConnectionSaga', () => {
    it('dispatches success when connection test passes', () => {
      const action = { type: adminActions.testConnectionRequest.type, payload: 'sp-1' }
      const adminState = {
        ...initialState,
        storageProviders: {
          ...initialState.storageProviders,
          data: [mockStorageProvider],
        },
      }
      const iterator = handleTestConnectionSaga(action) as Generator<unknown, void, unknown>
      iterator.next()
      expect(iterator.next(adminState).value).toEqual(
        call([adminService, adminService.testConnection], 'sp-1', mockStorageProvider.bucket),
      )
      expect(iterator.next({ status: 'success' }).value).toEqual(
        put(adminActions.testConnectionSuccess('sp-1')),
      )
      expect(iterator.next().value).toEqual(delay(2500))
      expect(iterator.next().value).toEqual(put(adminActions.resetConnectionTest('sp-1')))
    })

    it('dispatches failure when connection test throws', () => {
      const action = { type: adminActions.testConnectionRequest.type, payload: 'sp-1' }
      const adminState = {
        ...initialState,
        storageProviders: {
          ...initialState.storageProviders,
          data: [mockStorageProvider],
        },
      }
      const iterator = handleTestConnectionSaga(action) as Generator<unknown, void, unknown>
      iterator.next()
      iterator.next(adminState)
      const error = new Error('Connection failed')
      expect(iterator.throw(error).value).toEqual(put(adminActions.testConnectionFailure('sp-1')))
    })
  })

  describe('adminSaga root watcher', () => {
    it('registers takeLatest for all admin actions', () => {
      const iterator = adminSaga()
      expect(iterator.next().value).toEqual(
        takeLatest(adminActions.testConnectionRequest.type, handleTestConnectionSaga),
      )
      expect(iterator.next().value).toEqual(
        takeLatest(adminActions.fetchWorkspacesRequest.type, handleFetchWorkspacesSaga),
      )
      expect(iterator.next().value).toEqual(
        takeLatest(adminActions.fetchProvidersRequest.type, handleFetchProvidersSaga),
      )
      expect(iterator.next().value).toEqual(
        takeLatest(adminActions.createProviderRequest.type, handleCreateProviderSaga),
      )
      expect(iterator.next().value).toEqual(
        takeLatest(adminActions.updateProviderRequest.type, handleUpdateProviderSaga),
      )
      expect(iterator.next().value).toEqual(
        takeLatest(adminActions.deleteProviderRequest.type, handleDeleteProviderSaga),
      )
      expect(iterator.next().done).toBe(true)
    })
  })
})
