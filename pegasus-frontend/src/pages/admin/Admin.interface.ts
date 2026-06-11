export interface WorkspaceItem {
  id: string;
  name: string;
  isDefault: boolean;
  createdDate: string;
  userCount: number;
  status: 'Active' | 'Restricted' | 'Archived';
}

export interface StorageProviderItem {
  id: string;
  name: string;
  providerType: 'Google Cloud Storage' | 'Amazon S3' | 'Local File System' | 'Azure Blob Storage';
  status: 'Success' | 'Syncing';
  pathLabel: string;
  pathValue: string;
  syncTime: string;
  regionLabel: string;
  regionValue: string;
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
    testingConnectionId: string | null; // Tracks which connection is currently being tested
    testResult: { [key: string]: 'success' | 'failed' | null };
    error: string | null;
  };
}