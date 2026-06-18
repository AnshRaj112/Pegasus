import { type PayloadAction, createSlice } from '@reduxjs/toolkit';
import {
  type AdminReducerState,
  type CreateStorageProviderPayload,
  type StorageProviderItem,
  type StorageProviderPayload,
  type WorkspaceItem,
} from './Admin.interface';

export const initialState: AdminReducerState = {
  activeSubSection: 'workspace',
  workspaces: {
    data: [
      { id: 'w1', name: 'Global Workspace', isDefault: true, createdDate: 'Jan 12, 2023', userCount: 842, status: 'Active' },
      { id: 'w2', name: 'Production (US-East)', isDefault: false, createdDate: 'Mar 05, 2023', userCount: 215, status: 'Active' },
      { id: 'w3', name: 'Quality Assurance (Staging)', isDefault: false, createdDate: 'Jun 18, 2023', userCount: 42, status: 'Active' },
      { id: 'w4', name: 'External Client Sandbox', isDefault: false, createdDate: 'Aug 22, 2023', userCount: 12, status: 'Restricted' },
      { id: 'w5', name: 'Legacy Audit (ReadOnly)', isDefault: false, createdDate: 'Dec 01, 2022', userCount: 4, status: 'Archived' },
    ],
    isFetching: false,
    error: null,
  },
  storageProviders: {
    data: [],
    isFetching: false,
    isCreating: false,
    isUpdating: false,
    isDeletingId: null,
    testingConnectionId: null,
    testResult: {},
    error: null,
    createError: null,
    updateError: null,
  },
};

const adminSlice = createSlice({
  name: 'admin',
  initialState,
  reducers: {
    setSubSection: (state, action: PayloadAction<'store' | 'workspace'>) => ({
      ...state,
      activeSubSection: action.payload,
    }),

    fetchWorkspacesRequest: (state) => {
      state.workspaces.isFetching = true;
      state.workspaces.error = null;
    },
    fetchWorkspacesSuccess: (state, action: PayloadAction<WorkspaceItem[]>) => {
      state.workspaces.isFetching = false;
      state.workspaces.data = action.payload;
    },
    fetchWorkspacesError: (state, action: PayloadAction<string>) => {
      state.workspaces.isFetching = false;
      state.workspaces.error = action.payload;
    },
    deleteWorkspace: (state, action: PayloadAction<string>) => {
      state.workspaces.data = state.workspaces.data.filter((w) => w.id !== action.payload);
    },

    fetchProvidersRequest: (state) => {
      state.storageProviders.isFetching = true;
      state.storageProviders.error = null;
    },
    fetchProvidersSuccess: (state, action: PayloadAction<StorageProviderItem[]>) => {
      state.storageProviders.isFetching = false;
      state.storageProviders.data = action.payload;
    },
    fetchProvidersError: (state, action: PayloadAction<string>) => {
      state.storageProviders.isFetching = false;
      state.storageProviders.error = action.payload;
    },

    createProviderRequest: (state, _action: PayloadAction<CreateStorageProviderPayload>) => {
      state.storageProviders.isCreating = true;
      state.storageProviders.createError = null;
    },
    createProviderSuccess: (state, action: PayloadAction<StorageProviderItem>) => {
      state.storageProviders.isCreating = false;
      state.storageProviders.data = [action.payload, ...state.storageProviders.data];
    },
    createProviderError: (state, action: PayloadAction<string>) => {
      state.storageProviders.isCreating = false;
      state.storageProviders.createError = action.payload;
    },
    clearCreateProviderError: (state) => {
      state.storageProviders.createError = null;
    },

    updateProviderRequest: (state, _action: PayloadAction<StorageProviderPayload>) => {
      state.storageProviders.isUpdating = true;
      state.storageProviders.updateError = null;
    },
    updateProviderSuccess: (state, action: PayloadAction<StorageProviderItem>) => {
      state.storageProviders.isUpdating = false;
      state.storageProviders.data = state.storageProviders.data.map((p) =>
        p.id === action.payload.id ? action.payload : p,
      );
    },
    updateProviderError: (state, action: PayloadAction<string>) => {
      state.storageProviders.isUpdating = false;
      state.storageProviders.updateError = action.payload;
    },
    clearUpdateProviderError: (state) => {
      state.storageProviders.updateError = null;
    },

    deleteProviderRequest: (state, action: PayloadAction<string>) => {
      state.storageProviders.isDeletingId = action.payload;
    },
    deleteProviderSuccess: (state, action: PayloadAction<string>) => {
      state.storageProviders.isDeletingId = null;
      state.storageProviders.data = state.storageProviders.data.filter((p) => p.id !== action.payload);
    },
    deleteProviderError: (state, action: PayloadAction<string>) => {
      state.storageProviders.isDeletingId = null;
      state.storageProviders.error = action.payload;
    },

    testConnectionRequest: (state, action: PayloadAction<string>) => {
      state.storageProviders.testingConnectionId = action.payload;
      state.storageProviders.testResult[action.payload] = null;
    },
    testConnectionSuccess: (state, action: PayloadAction<string>) => {
      state.storageProviders.testingConnectionId = null;
      state.storageProviders.testResult[action.payload] = 'success';
    },
    testConnectionFailure: (state, action: PayloadAction<string>) => {
      state.storageProviders.testingConnectionId = null;
      state.storageProviders.testResult[action.payload] = 'failed';
    },
    resetConnectionTest: (state, action: PayloadAction<string>) => {
      state.storageProviders.testResult[action.payload] = null;
    },
  },
});

export const adminActions = { ...adminSlice.actions };
export default adminSlice.reducer;
