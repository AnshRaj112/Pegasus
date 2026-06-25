import {
  Api,
  type CloudConnection,
  type CloudConnectionCreateRequest,
  type CloudConnectionUpdateRequest,
} from '../../shared/api/Api';

import {
  type CreateStorageProviderPayload,
  type StorageProviderItem,
  type StorageProviderPayload,
  type StorageProviderType,
} from './Admin.interface';

const PROVIDER_LABELS: Record<string, StorageProviderType> = {
  'google-cloud-storage': 'Google Cloud Storage',
  'amazon-s3': 'Amazon S3',
  'azure-blob-storage': 'Azure Blob Storage',
  'local': 'Local File System',
};

const formatTimestamp = (iso: string | undefined): string => {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const mapConnection = (conn: CloudConnection): StorageProviderItem => {
  const providerType = PROVIDER_LABELS[conn.provider] ?? 'Google Cloud Storage';
  const bucket = conn.bucket?.trim() ?? '';
  return {
    id: conn.id,
    name: conn.name,
    providerType,
    provider: conn.provider,
    bucket,
    projectId: conn.project_id,
    active: conn.active,
    status: conn.active ? 'Success' : 'Inactive',
    pathLabel: 'Bucket:',
    pathValue: bucket ? `gs://${bucket}` : 'All accessible buckets',
    syncTime: formatTimestamp(conn.updated_at ?? conn.created_at),
    regionLabel: 'Project ID:',
    regionValue: conn.project_id?.trim() || '—',
  };
};

class AdminService {
  async fetchWorkspaces() {
    return [];
  }

  async fetchStorageProviders(): Promise<StorageProviderItem[]> {
    const { data } = await Api.listCloudConnections();
    return data.map(mapConnection);
  }

  async createStorageProvider(payload: CreateStorageProviderPayload): Promise<StorageProviderItem> {
    const body: CloudConnectionCreateRequest = {
      name: payload.name.trim(),
      provider: payload.provider ?? 'google-cloud-storage',
      bucket: payload.bucket.trim(),
      project_id: payload.projectId?.trim() || null,
      credentials_json: payload.credentialsJson,
      active: true,
    };
    const { data } = await Api.createCloudConnection(body);
    return mapConnection(data);
  }

  async updateStorageProvider(payload: StorageProviderPayload): Promise<StorageProviderItem> {
    if (!payload.id) {
      throw new Error('Connection id is required to update.');
    }
    const body: CloudConnectionUpdateRequest = {
      name: payload.name.trim(),
      provider: payload.provider ?? 'google-cloud-storage',
      bucket: payload.bucket.trim(),
      project_id: payload.projectId?.trim() || null,
    };
    if (payload.credentialsJson?.trim()) {
      body.credentials_json = payload.credentialsJson.trim();
    }
    const { data } = await Api.updateCloudConnection(payload.id, body);
    return mapConnection(data);
  }

  async deleteStorageProvider(connectionId: string): Promise<void> {
    await Api.deleteCloudConnection(connectionId);
  }

  async testConnection(connectionId: string, bucket?: string): Promise<{ status: 'success' | 'failed' }> {
    await Api.browseCloud({
      connection_id: connectionId,
      bucket: bucket?.trim() ? bucket : null,
      prefix: '',
      file_format: 'auto',
    });
    return { status: 'success' };
  }
}

export const adminService = new AdminService();
