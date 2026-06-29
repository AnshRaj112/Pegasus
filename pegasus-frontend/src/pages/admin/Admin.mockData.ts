import { AxiosError, AxiosHeaders } from 'axios'

import { initializeEmptyState } from '~/shared/constants/common.constants'

import {
  CreateStorageProviderPayload,
  StorageProviderItem,
  WorkspaceItem,
} from './Admin.interface'
import { initialState } from './Admin.reducer'

export const mockWorkspaceItems: WorkspaceItem[] = [
  {
    id: 'w-test',
    name: 'Test Workspace',
    isDefault: true,
    createdDate: 'Jan 12, 2023',
    userCount: 42,
    status: 'Active',
  },
]

export const mockStorageProvider: StorageProviderItem = {
  id: 'sp-1',
  name: 'Test GCS Connection',
  providerType: 'Google Cloud Storage',
  provider: 'google-cloud-storage',
  bucket: 'test-bucket',
  projectId: 'test-project',
  active: true,
  status: 'Success',
  pathLabel: 'Bucket:',
  pathValue: 'gs://test-bucket',
  syncTime: 'Jan 01, 2024',
  regionLabel: 'Project ID:',
  regionValue: 'test-project',
}

export const mockCreateProviderPayload: CreateStorageProviderPayload = {
  name: 'New Connection',
  bucket: 'new-bucket',
  projectId: 'new-project',
  credentialsJson: '{"type":"service_account"}',
}

export const mockUpdateProviderPayload = {
  id: 'sp-1',
  name: 'Updated Connection',
  bucket: 'updated-bucket',
  projectId: 'updated-project',
}

export const mockAxiosError = new AxiosError(
  'Server error',
  'ERR_BAD_REQUEST',
  undefined,
  undefined,
  {
    status: 500,
    statusText: 'Internal Server Error',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: { message: 'Server error' },
  },
)

export const workspacesLoading = {
  ...initialState.workspaces,
  isFetching: true,
  error: null,
}

export const workspacesSuccess = {
  ...initialState.workspaces,
  data: mockWorkspaceItems,
  isFetching: false,
  error: null,
}

export const workspacesError = {
  ...initialState.workspaces,
  isFetching: false,
  error: 'Failed to fetch workspaces',
}

export const providersLoading = {
  ...initialState.storageProviders,
  data: [],
  isFetching: true,
  error: null,
}

export const providersSuccess = {
  ...initialState.storageProviders,
  data: [mockStorageProvider],
  isFetching: false,
  error: null,
}

export const providersError = {
  ...initialState.storageProviders,
  isFetching: false,
  error: 'Failed to fetch storage connections',
}

export const providersCreating = {
  ...initialState.storageProviders,
  isCreating: true,
  createError: null,
}

export const providersCreateError = {
  ...initialState.storageProviders,
  isCreating: false,
  createError: 'Failed to create storage connection',
}

export const emptyProvidersState = {
  ...initialState.storageProviders,
  ...initializeEmptyState,
}
