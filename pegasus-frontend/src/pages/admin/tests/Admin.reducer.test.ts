import adminReducer, { adminActions, initialState } from '../Admin.reducer'
import {
  mockCreateProviderPayload,
  mockStorageProvider,
  mockUpdateProviderPayload,
  mockWorkspaceItems,
  providersCreateError,
  providersCreating,
  providersError,
  providersLoading,
  providersSuccess,
  workspacesError,
  workspacesLoading,
  workspacesSuccess,
} from '../Admin.mockData'

describe('Admin reducer', () => {
  it('returns initial state for unknown action', () => {
    expect(adminReducer(undefined, { type: 'unknown' })).toEqual(initialState)
  })

  describe('workspaces', () => {
    it('sets loading on fetchWorkspacesRequest', () => {
      expect(adminReducer(initialState, adminActions.fetchWorkspacesRequest())).toEqual({
        ...initialState,
        workspaces: workspacesLoading,
      })
    })

    it('stores data on fetchWorkspacesSuccess', () => {
      expect(adminReducer(initialState, adminActions.fetchWorkspacesSuccess(mockWorkspaceItems))).toEqual({
        ...initialState,
        workspaces: workspacesSuccess,
      })
    })

    it('stores error on fetchWorkspacesError', () => {
      expect(adminReducer(initialState, adminActions.fetchWorkspacesError('Failed to fetch workspaces'))).toEqual({
        ...initialState,
        workspaces: workspacesError,
      })
    })

    it('removes workspace on deleteWorkspace', () => {
      const stateWithWorkspaces = { ...initialState, workspaces: workspacesSuccess }
      expect(adminReducer(stateWithWorkspaces, adminActions.deleteWorkspace('w-test'))).toEqual({
        ...stateWithWorkspaces,
        workspaces: {
          ...workspacesSuccess,
          data: [],
        },
      })
    })
  })

  describe('storage providers', () => {
    it('sets loading on fetchProvidersRequest', () => {
      expect(adminReducer(initialState, adminActions.fetchProvidersRequest())).toEqual({
        ...initialState,
        storageProviders: providersLoading,
      })
    })

    it('stores data on fetchProvidersSuccess', () => {
      expect(adminReducer(initialState, adminActions.fetchProvidersSuccess([mockStorageProvider]))).toEqual({
        ...initialState,
        storageProviders: providersSuccess,
      })
    })

    it('stores error on fetchProvidersError', () => {
      expect(
        adminReducer(initialState, adminActions.fetchProvidersError('Failed to fetch storage connections')),
      ).toEqual({
        ...initialState,
        storageProviders: providersError,
      })
    })

    it('sets isCreating on createProviderRequest', () => {
      expect(
        adminReducer(initialState, adminActions.createProviderRequest(mockCreateProviderPayload)),
      ).toEqual({
        ...initialState,
        storageProviders: providersCreating,
      })
    })

    it('prepends provider on createProviderSuccess', () => {
      const state = { ...initialState, storageProviders: providersSuccess }
      const created = { ...mockStorageProvider, id: 'sp-new', name: 'New Connection' }
      const result = adminReducer(state, adminActions.createProviderSuccess(created))
      expect(result.storageProviders.data[0]).toEqual(created)
      expect(result.storageProviders.isCreating).toBe(false)
    })

    it('stores createError on createProviderError', () => {
      expect(
        adminReducer(initialState, adminActions.createProviderError('Failed to create storage connection')),
      ).toEqual({
        ...initialState,
        storageProviders: providersCreateError,
      })
    })

    it('clears createError on clearCreateProviderError', () => {
      const state = { ...initialState, storageProviders: providersCreateError }
      expect(adminReducer(state, adminActions.clearCreateProviderError()).storageProviders.createError).toBeNull()
    })

    it('updates provider on updateProviderSuccess', () => {
      const state = { ...initialState, storageProviders: providersSuccess }
      const updated = { ...mockStorageProvider, name: 'Updated Connection' }
      expect(adminReducer(state, adminActions.updateProviderSuccess(updated)).storageProviders.data[0].name).toBe(
        'Updated Connection',
      )
    })

    it('sets isUpdating on updateProviderRequest', () => {
      const result = adminReducer(initialState, adminActions.updateProviderRequest(mockUpdateProviderPayload))
      expect(result.storageProviders.isUpdating).toBe(true)
      expect(result.storageProviders.updateError).toBeNull()
    })

    it('stores updateError on updateProviderError', () => {
      const result = adminReducer(initialState, adminActions.updateProviderError('Update failed'))
      expect(result.storageProviders.isUpdating).toBe(false)
      expect(result.storageProviders.updateError).toBe('Update failed')
    })

    it('sets isDeletingId on deleteProviderRequest', () => {
      const result = adminReducer(initialState, adminActions.deleteProviderRequest('sp-1'))
      expect(result.storageProviders.isDeletingId).toBe('sp-1')
    })

    it('removes provider on deleteProviderSuccess', () => {
      const state = { ...initialState, storageProviders: providersSuccess }
      expect(adminReducer(state, adminActions.deleteProviderSuccess('sp-1')).storageProviders.data).toEqual([])
    })

    it('stores delete error on deleteProviderError', () => {
      const state = {
        ...initialState,
        storageProviders: { ...providersSuccess, isDeletingId: 'sp-1' },
      }
      const result = adminReducer(state, adminActions.deleteProviderError('Delete failed'))
      expect(result.storageProviders.isDeletingId).toBeNull()
      expect(result.storageProviders.error).toBe('Delete failed')
    })

    describe('connection test', () => {
      it('sets testingConnectionId on testConnectionRequest', () => {
      const result = adminReducer(initialState, adminActions.testConnectionRequest('sp-1'))
      expect(result.storageProviders.testingConnectionId).toBe('sp-1')
      expect(result.storageProviders.testResult['sp-1']).toBeNull()
    })

    it('records success on testConnectionSuccess', () => {
      const state = {
        ...initialState,
        storageProviders: { ...providersSuccess, testingConnectionId: 'sp-1' },
      }
      const result = adminReducer(state, adminActions.testConnectionSuccess('sp-1'))
      expect(result.storageProviders.testingConnectionId).toBeNull()
      expect(result.storageProviders.testResult['sp-1']).toBe('success')
    })

    it('records failure on testConnectionFailure', () => {
      const state = {
        ...initialState,
        storageProviders: { ...providersSuccess, testingConnectionId: 'sp-1' },
      }
      const result = adminReducer(state, adminActions.testConnectionFailure('sp-1'))
      expect(result.storageProviders.testingConnectionId).toBeNull()
      expect(result.storageProviders.testResult['sp-1']).toBe('failed')
    })

    it('clears test result on resetConnectionTest', () => {
      const state = {
        ...initialState,
        storageProviders: {
          ...providersSuccess,
          testResult: { 'sp-1': 'success' as const },
        },
      }
      expect(adminReducer(state, adminActions.resetConnectionTest('sp-1')).storageProviders.testResult['sp-1']).toBeNull()
      })
    })
  })
})
