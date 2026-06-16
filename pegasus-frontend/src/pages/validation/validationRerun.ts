import type {
  CloudConnection,
  ColumnMapping,
  GoogleCloudStorageConfig,
  ValidateRequest,
  ValidationHistoryDetail,
} from '../../shared/api/Api';
import type { ValidationFormState } from './Validation.interface';
import { gcsUri } from '../report/reportPairId';

export const parseGsUri = (uri: string): GoogleCloudStorageConfig | null => {
  const trimmed = uri.trim();
  const match = /^gs:\/\/([^/]+)\/(.+)$/.exec(trimmed);
  if (!match) return null;
  return {
    provider: 'google-cloud-storage',
    bucket: match[1],
    object_name: match[2],
  };
};

export const cloudFromPath = (path: string | null | undefined): GoogleCloudStorageConfig | null => {
  if (!path) return null;
  if (path.startsWith('gs://')) return parseGsUri(path);
  return null;
};

export const cloudHasAuth = (cloud: GoogleCloudStorageConfig | null | undefined): boolean =>
  Boolean(cloud?.connection_id || (cloud?.credentials_json ?? '').trim());

export const enrichCloudWithConnection = (
  cloud: GoogleCloudStorageConfig | null,
  connections: CloudConnection[],
): GoogleCloudStorageConfig | null => {
  if (!cloud || cloudHasAuth(cloud)) return cloud;
  const bucket = (cloud.bucket ?? '').trim();
  const conn = connections.find((c) => c.active && c.bucket.trim() === bucket);
  if (!conn) return cloud;
  return { ...cloud, connection_id: conn.id };
};

export const enrichFormWithConnections = (
  form: Partial<ValidationFormState>,
  connections: CloudConnection[],
): Partial<ValidationFormState> => ({
  ...form,
  sourceCloud: enrichCloudWithConnection(form.sourceCloud ?? null, connections),
  targetCloud: enrichCloudWithConnection(form.targetCloud ?? null, connections),
  connectionId: form.connectionId
    ?? connections.find((c) => c.active && c.bucket.trim() === (form.sourceCloud?.bucket ?? '').trim())?.id
    ?? null,
});

export const formFromHistory = (detail: ValidationHistoryDetail): Partial<ValidationFormState> => {
  const sourceCloud = cloudFromPath(detail.source_path);
  const targetCloud = cloudFromPath(detail.target_path);
  return {
    sourceCloud,
    targetCloud,
    sourceFileName: detail.source_filename,
    targetFileName: detail.target_filename,
    uidColumn: detail.uid_column,
    delimiter: detail.delimiter || 'auto',
    hasHeader: true,
    columnMappings: (detail.column_mappings ?? []) as ColumnMapping[],
  };
};

/**
 * Build validate request. When cloud refs lack credentials, send gs:// paths so the
 * backend resolves the admin connection by bucket (same as first-time wizard flow).
 */
export const validateRequestFromForm = (
  form: ValidationFormState,
  pathOverride?: { source_path?: string | null; target_path?: string | null },
): ValidateRequest => {
  const base = {
    uid_column: form.uidColumn,
    delimiter: form.delimiter || 'auto',
    has_header: form.hasHeader,
    column_mappings: form.columnMappings,
  };

  const srcPath = pathOverride?.source_path
    ?? (form.sourceCloud ? gcsUri(form.sourceCloud) : null);
  const tgtPath = pathOverride?.target_path
    ?? (form.targetCloud ? gcsUri(form.targetCloud) : null);

  if (
    form.sourceCloud
    && form.targetCloud
    && cloudHasAuth(form.sourceCloud)
    && cloudHasAuth(form.targetCloud)
  ) {
    return { ...base, source_cloud: form.sourceCloud, target_cloud: form.targetCloud };
  }

  if (srcPath && tgtPath) {
    return { ...base, source_path: srcPath, target_path: tgtPath };
  }

  return {
    ...base,
    source_cloud: form.sourceCloud,
    target_cloud: form.targetCloud,
    source_path: srcPath,
    target_path: tgtPath,
  };
};
