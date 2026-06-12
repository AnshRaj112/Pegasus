/**
 * Central API client for Pegasus dashboard + validation features.
 * Base URL: `${VITE_API_BASE}/api/v1` (empty VITE_API_BASE → same-origin /api via nginx).
 */
import { type AxiosResponse } from 'axios';

import { isTransientPollError } from './apiError';
import { httpClient } from './httpClient';

/** Completion polls may build a large JSON payload; allow up to 10 minutes per request. */
const JOB_POLL_TIMEOUT_MS = 600_000;
const POLL_INTERVAL_MS = 2_000;
const MAX_POLL_BACKOFF_MS = 30_000;

// ─── Request / response types ───────────────────────────────────────────────

export interface ColumnMapping {
  source_column: string;
  target_column: string;
  source_columns?: string[];
  target_columns?: string[];
  compare_mode?: string;
  structured_order_sensitive?: boolean;
}

export interface GoogleCloudStorageConfig {
  provider?: 'google-cloud-storage';
  bucket?: string | null;
  object_name: string;
  connection_id?: string | null;
  credentials_json?: string | null;
  project_id?: string | null;
}

export interface ValidateRequest {
  source_path?: string | null;
  target_path?: string | null;
  source_cloud?: GoogleCloudStorageConfig | null;
  target_cloud?: GoogleCloudStorageConfig | null;
  uid_column?: string;
  delimiter?: string;
  column_mappings?: ColumnMapping[];
  has_header?: boolean;
  file_format?: string;
}

export interface CloudBrowseRequest {
  bucket?: string | null;
  prefix?: string;
  connection_id?: string | null;
  credentials_json?: string | null;
  project_id?: string | null;
  file_format?: string;
}

export interface CloudBrowseEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size_bytes?: number | null;
}

export interface CloudBrowseResponse {
  bucket: string;
  prefix: string;
  parent_prefix: string | null;
  entries: CloudBrowseEntry[];
  truncated?: boolean;
}

export interface CloudFileProfileRequest {
  cloud: GoogleCloudStorageConfig;
  delimiter?: string;
  has_header?: boolean;
}

export interface CloudFileProfileResponse {
  object_name: string;
  gcs_uri: string;
  file_size_bytes: number;
  file_format: string;
  suggested_file_format?: string | null;
  dataset_model?: string | null;
  column_count: number;
  row_count: number;
  delimiter?: string | null;
  has_header?: boolean;
}

export interface CloudConnection {
  id: string;
  name: string;
  provider: string;
  bucket: string;
  project_id: string | null;
  active: boolean;
}

export interface LocalColumnPreviewResponse {
  source_columns: string[];
  target_columns: string[];
  compare_columns: string[];
  auto_mappings: Array<{ source_column: string; target_column: string }>;
  unmatched_source_columns: string[];
  unmatched_target_columns: string[];
  delimiter: string;
  has_header?: boolean;
  inferred_has_header?: boolean | null;
  source_samples: Record<string, string[]>;
  target_samples: Record<string, string[]>;
  complex_columns?: string[];
  needs_order_preference?: boolean;
}

export interface ValidationJobAcceptedResponse {
  job_id: string;
  status: string;
  poll_url: string;
}

export interface MismatchCounts {
  missing_in_target: number;
  extra_in_target: number;
  value_mismatch: number;
}

export interface MismatchSampleRow {
  uid: string;
  mismatch_type: string;
  column_name: string | null;
  source_value: string | null;
  target_value: string | null;
  row_detail?: Record<string, unknown> | string | null;
}

export interface ValidateResult {
  summary: {
    source_row_count: number;
    target_row_count: number;
    compared_column_count?: number;
    total_mismatch_records: number;
    is_match: boolean;
  };
  mismatch_counts: MismatchCounts;
  mismatch_sample_groups: {
    missing_in_target: MismatchSampleRow[];
    extra_in_target: MismatchSampleRow[];
    value_mismatch: MismatchSampleRow[];
  };
  run_id: string | null;
  compared_columns?: string[];
  durations?: { validation_seconds?: number; total_seconds?: number };
}

export interface ValidationJobDetailResponse {
  status: string;
  error?: string | null;
  result?: ValidateResult | null;
}

export interface ValidationMismatchesResponse {
  run_id: string;
  items: MismatchSampleRow[];
  total: number;
  offset: number;
  limit: number;
}

export interface ValidationHistoryDetail {
  run_id: string;
  status: string;
  source_path: string | null;
  target_path: string | null;
  source_filename: string | null;
  target_filename: string | null;
  uid_column: string;
  delimiter: string;
  is_match: boolean | null;
  mismatch_counts: MismatchCounts;
  source_row_count: number | null;
  target_row_count: number | null;
  compared_column_count: number | null;
  compared_columns: string[];
  durations?: { validation_seconds?: number; total_seconds?: number };
}

export interface QueueJobSnapshot {
  job_id: string;
  state: string;
  enqueued_at: number;
  started_at: number | null;
  finished_at: number | null;
}

export interface QueueStatusResponse {
  running: number;
  pending: number;
  jobs: QueueJobSnapshot[];
}

export interface DailyStatRow {
  date: string;
  passed: number;
  failed: number;
  total: number;
}

export interface DailyStatsResponse {
  items: DailyStatRow[];
  totals: { passed: number; failed: number; total: number };
}

export interface EntityInsight {
  inferred_entity: string;
  display_name: string;
  confidence: string;
  success_count: number;
  failed_count: number;
  total_count: number;
}

export interface EntityInsightsResponse {
  limit: number;
  entities: EntityInsight[];
}

export interface CreateEntityRequest {
  display_name: string;
  aliases?: string[];
}

export interface SaveDraftRequest {
  source_path: string;
  target_path: string;
  uid_column: string;
  delimiter?: string;
  column_mappings?: ColumnMapping[];
}

// ─── Endpoints ────────────────────────────────────────────────────────────────

const E = {
  health: '/health',
  validateQueue: '/validate/queue',
  validateLocal: '/validate/local',
  validateLocalColumns: '/validate/local/columns',
  validateCloudBrowse: '/validate/cloud/browse',
  validateCloudProfile: '/validate/cloud/profile',
  cloudConnections: '/admin/cloud-connections',
  validateJob: (jobId: string) => `/validate/jobs/${jobId}`,
  validateDailyStats: '/validate/history/daily-stats',
  validateEntityInsights: '/validate/history/entities/insights',
  validateCreateEntity: '/validate/history/entities',
  validateHistoryDraft: '/validate/history/draft',
  validateHistoryRun: (runId: string) => `/validate/history/${runId}`,
  validateHistoryMismatches: (runId: string) => `/validate/history/${runId}/mismatches`,
} as const;

// ─── API methods ────────────────────────────────────────────────────────────

export const Api = {
  /** GET /health — liveness probe */
  getHealth: (): Promise<AxiosResponse<{ status: string }>> => httpClient.get(E.health),

  /** GET /validate/queue — active validation jobs for dashboard task list */
  getValidationQueue: (): Promise<AxiosResponse<QueueStatusResponse>> =>
    httpClient.get(E.validateQueue),

  /** GET /validate/history/daily-stats?days=7 — pass/fail chart + metric totals */
  getDailyStats: (days = 7): Promise<AxiosResponse<DailyStatsResponse>> =>
    httpClient.get(E.validateDailyStats, { params: { days } }),

  /** GET /validate/history/entities/insights — entity workspaces for dashboard */
  getEntityInsights: (limit = 50): Promise<AxiosResponse<EntityInsightsResponse>> =>
    httpClient.get(E.validateEntityInsights, { params: { limit } }),

  /** POST /validate/history/entities — register entity for filename inference */
  createEntity: (body: CreateEntityRequest): Promise<AxiosResponse<unknown>> =>
    httpClient.post(E.validateCreateEntity, body),

  /** GET /admin/cloud-connections — saved GCS connection profiles (admin session cookie) */
  listCloudConnections: (): Promise<AxiosResponse<CloudConnection[]>> =>
    httpClient.get(E.cloudConnections),

  /** POST /validate/cloud/browse — list GCS prefixes/objects under a bucket prefix */
  browseCloud: (body: CloudBrowseRequest): Promise<AxiosResponse<CloudBrowseResponse>> =>
    httpClient.post(E.validateCloudBrowse, body),

  /** POST /validate/cloud/profile — detect format and row/column counts for one GCS object */
  profileCloudFile: (body: CloudFileProfileRequest): Promise<AxiosResponse<CloudFileProfileResponse>> =>
    httpClient.post(E.validateCloudProfile, body),

  /** POST /validate/local/columns — header preview (supports source_cloud / target_cloud) */
  previewValidationColumns: (body: ValidateRequest): Promise<AxiosResponse<LocalColumnPreviewResponse>> =>
    httpClient.post(E.validateLocalColumns, body),

  /** POST /validate/local — queue validation job (202); use source_cloud + target_cloud for GCS */
  submitValidation: (body: ValidateRequest): Promise<AxiosResponse<ValidationJobAcceptedResponse>> =>
    httpClient.post(E.validateLocal, body),

  /** GET /validate/jobs/{job_id} — poll job status/result */
  getValidationJob: (jobId: string): Promise<AxiosResponse<ValidationJobDetailResponse>> =>
    httpClient.get(E.validateJob(jobId), { timeout: JOB_POLL_TIMEOUT_MS }),

  /** Poll until completed or failed; retries transient network/gateway errors. */
  pollValidationUntilComplete: async (jobId: string): Promise<ValidateResult> => {
    let backoffMs = POLL_INTERVAL_MS;
    for (;;) {
      try {
        const { data } = await Api.getValidationJob(jobId);
        backoffMs = POLL_INTERVAL_MS;
        if (data.status === 'completed' && data.result) return data.result;
        if (data.status === 'failed') throw new Error(data.error || 'Validation failed');
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      } catch (error) {
        if (!isTransientPollError(error)) throw error;
        await new Promise((r) => setTimeout(r, backoffMs));
        backoffMs = Math.min(Math.round(backoffMs * 1.5), MAX_POLL_BACKOFF_MS);
      }
    }
  },

  /** GET /validate/history/{run_id} — persisted run summary (fallback when job poll expires) */
  getValidationHistoryRun: (runId: string): Promise<AxiosResponse<ValidationHistoryDetail>> =>
    httpClient.get(E.validateHistoryRun(runId)),

  /** GET /validate/history/{run_id}/mismatches — paginated report rows */
  getValidationMismatches: (
    runId: string,
    params: { limit: number; offset: number; mismatch_type?: string },
  ): Promise<AxiosResponse<ValidationMismatchesResponse>> =>
    httpClient.get(E.validateHistoryMismatches(runId), { params }),

  /** POST /validate/history/draft — save mapping without running */
  saveValidationDraft: (body: SaveDraftRequest): Promise<AxiosResponse<unknown>> =>
    httpClient.post(E.validateHistoryDraft, body),
};
