export interface WorkspaceItem {
  id: string;
  name: string;
  isDefault: boolean;
  createdDate: string;
  userCount: number;
  status: 'Active' | 'Restricted' | 'Archived';
}

export type StorageProviderType = 'Google Cloud Storage' | 'Amazon S3' | 'Local File System' | 'Azure Blob Storage';

export interface StorageProviderItem {
  id: string;
  name: string;
  providerType: StorageProviderType;
  provider: string;
  bucket: string;
  projectId: string | null;
  active: boolean;
  status: 'Success' | 'Inactive';
  pathLabel: string;
  pathValue: string;
  syncTime: string;
  regionLabel: string;
  regionValue: string;
}

export interface CreateStorageProviderPayload {
  name: string;
  bucket: string;
  projectId?: string;
  credentialsJson: string;
  provider?: string;
}

export interface AdminReducerState {
  activeSubSection: 'store' | 'workspace';
  workspaces: {
    data: WorkspaceItem[];
    isFetching: boolean;
    error: string | null;
  };
  storageProviders: {
    data: StorageProviderItem[];
    isFetching: boolean;
    isCreating: boolean;
    isDeletingId: string | null;
    testingConnectionId: string | null;
    testResult: { [key: string]: 'success' | 'failed' | null };
    error: string | null;
    createError: string | null;
  };
}