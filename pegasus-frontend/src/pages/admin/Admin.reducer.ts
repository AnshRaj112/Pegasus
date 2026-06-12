import { type PayloadAction, createSlice } from '@reduxjs/toolkit';
import { type AdminReducerState, type WorkspaceItem, type StorageProviderItem } from './Admin.interface';

// ⚡ HERE IS YOUR MOCK DATA LIVING INSIDE THE GLOBAL STATE ⚡
export const initialState: AdminReducerState = {
  activeSubSection: 'workspace',
  workspaces: { 
    data: [
      { id: 'w1', name: 'Global Workspace', isDefault: true, createdDate: 'Jan 12, 2023', userCount: 842, status: 'Active' },
      { id: 'w2', name: 'Production (US-East)', isDefault: false, createdDate: 'Mar 05, 2023', userCount: 215, status: 'Active' },
      { id: 'w3', name: 'Quality Assurance (Staging)', isDefault: false, createdDate: 'Jun 18, 2023', userCount: 42, status: 'Active' },
      { id: 'w4', name: 'External Client Sandbox', isDefault: false, createdDate: 'Aug 22, 2023', userCount: 12, status: 'Restricted' },
      { id: 'w5', name: 'Legacy Audit (ReadOnly)', isDefault: false, createdDate: 'Dec 01, 2022', userCount: 4, status: 'Archived' }
    ], 
    isFetching: false, 
    error: null 
  },
  storageProviders: { 
    data: [
      { id: 'p1', name: 'production-datalake-v1', providerType: 'Google Cloud Storage', status: 'Success', pathLabel: 'Bucket Path:', pathValue: 'gs://finance-prod-audit', syncTime: '2023-10-24 14:22:05', regionLabel: 'Region:', regionValue: 'us-east1' },
      { id: 'p2', name: 'staging-validation-store', providerType: 'Amazon S3', status: 'Syncing', pathLabel: 'Bucket Path:', pathValue: 's3://audit-staging-results', syncTime: '2023-10-24 15:10:44', regionLabel: 'Region:', regionValue: 'us-west-2' },
      { id: 'p3', name: 'local-dev-cache', providerType: 'Local File System', status: 'Success', pathLabel: 'System Path:', pathValue: '/mnt/data/audit_cache', syncTime: '2023-10-24 09:00:00', regionLabel: 'Mount Point:', regionValue: 'Ext4 Network Drive' },
      { id: 'p4', name: 'legacy-reports-archive', providerType: 'Azure Blob Storage', status: 'Success', pathLabel: 'Container:', pathValue: 'az://archive/2023-q3', syncTime: '2023-10-23 23:59:59', regionLabel: 'Region:', regionValue: 'UK South' }
    ], 
    isFetching: false, 
    testingConnectionId: null, 
    testResult: {}, 
    error: null 
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

    // --- Workspaces ---
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
      state.workspaces.data = state.workspaces.data.filter(w => w.id !== action.payload);
    },

    // --- Storage Providers ---
    fetchProvidersRequest: (state) => {
      state.storageProviders.isFetching = true;
      state.storageProviders.error = null;
    },
    fetchProvidersSuccess: (state, action: PayloadAction<StorageProviderItem[]>) => {
      state.storageProviders.isFetching = false;
      state.storageProviders.data = action.payload;
    },
    
    // Connection Testing
    testConnectionRequest: (state, action: PayloadAction<string>) => {
      state.storageProviders.testingConnectionId = action.payload;
      state.storageProviders.testResult[action.payload] = null;
    },
    testConnectionSuccess: (state, action: PayloadAction<string>) => {
      state.storageProviders.testingConnectionId = null;
      state.storageProviders.testResult[action.payload] = 'success';
    },
    resetConnectionTest: (state, action: PayloadAction<string>) => {
      state.storageProviders.testResult[action.payload] = null;
    },
  },
});

export const adminActions = { ...adminSlice.actions };
export default adminSlice.reducer;