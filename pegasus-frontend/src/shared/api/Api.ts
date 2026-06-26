/**
 * Central API client for Pegasus dashboard + validation features.
 * Base URL: `${VITE_API_BASE}/api/v1` (empty VITE_API_BASE → same-origin /api via nginx).
 */
import { AxiosResponse } from 'axios';

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
  is_sensitive?: boolean;
  source_regex_pattern?: string;
  source_regex_replacement?: string;
  target_regex_pattern?: string;
  target_regex_replacement?: string;
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
  fixed_width_config?: FixedWidthConfig;
  json_order_sensitive?: boolean;
  test_mode?: 'litmus' | 'full';
  mismatch_snippet_limit?: number | null;
}

export interface ValidationOptionsResponse {
  test_modes: ('litmus' | 'full')[];
  mismatch_snippet_limit_default: number;
  mismatch_snippet_limit_max: number;
}

export interface FixedWidthField {
  field_name: string;
  source_start: number;
  source_end: number;
  target_start: number;
  target_end: number;
  field_type?: string;
  structured_order_sensitive?: boolean;
  date_format?: string | null;
  source_date_format?: string | null;
  target_date_format?: string | null;
  compare_enabled?: boolean;
  is_sensitive?: boolean;
  source_regex_pattern?: string | null;
  source_regex_replacement?: string;
  target_regex_pattern?: string | null;
  target_regex_replacement?: string;
}

export interface FixedWidthConfig {
  uid_column?: string | null;
  fields: FixedWidthField[];
  match_strategy?: string;
}

export interface FixedWidthColumnPreview {
  field_name: string;
  source_start: number;
  source_end: number;
  target_start: number;
  target_end: number;
  field_type: string;
  width?: number;
  source_sample?: string;
  target_sample?: string;
  date_format?: string | null;
  source_date_format?: string | null;
  target_date_format?: string | null;
  structured_order_sensitive?: boolean;
  compare_enabled?: boolean;
  is_sensitive?: boolean;
  source_regex_pattern?: string | null;
  source_regex_replacement?: string;
  target_regex_pattern?: string | null;
  target_regex_replacement?: string;
}

export interface FixedWidthLayoutPreviewResponse {
  columns: FixedWidthColumnPreview[];
  suggested_join_column: string;
  source_sample: string;
  target_sample: string;
  line_width: number;
}

export interface JsonParentField {
  key: string;
  value_type: string;
}

export interface JsonParentMappingRow {
  source_parent: string | null;
  target_parent: string | null;
  ignored?: boolean;
  source_type?: string | null;
  target_type?: string | null;
}

export interface JsonParentPreviewResponse {
  document_mode: 'document' | 'ndjson' | string;
  source_parents: JsonParentField[];
  target_parents: JsonParentField[];
  suggested_mappings: JsonParentMappingRow[];
  suggested_uid_field?: string | null;
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
  created_at?: string | null;
  updated_at?: string | null;
  owner?: string | null;
  created_by?: string | null;
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
  json_preview?: string | null;
  archive_entry_count?: number | null;
  archive_entries_sample?: string[] | null;
  archive_manifest_supported?: boolean | null;
  archive_warnings?: string[] | null;
}

export interface CloudConnection {
  id: string;
  name: string;
  provider: string;
  bucket: string;
  project_id: string | null;
  active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface CloudConnectionCreateRequest {
  name: string;
  provider?: string;
  bucket?: string;
  project_id?: string | null;
  credentials_json: string;
  active?: boolean;
}

export interface CloudConnectionUpdateRequest {
  name?: string;
  provider?: string;
  bucket?: string;
  project_id?: string | null;
  credentials_json?: string;
  active?: boolean;
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
  sample_row_count?: number;
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
  value_mismatch_rows?: number;
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
  phase?: string | null;
  message?: string | null;
  error?: string | null;
  progress?: Record<string, unknown>;
  result?: ValidateResult | null;
  batch_result?: BatchValidateResponse | null;
}

export interface BatchUnitSpec {
  unit_id: string;
  source_paths: string[];
  target_paths: string[];
  uid_column?: string;
  column_mappings?: ColumnMapping[];
}

export interface BatchValidateRequest {
  file_format?: string;
  units: BatchUnitSpec[];
  on_unit_failure?: 'stop' | 'continue';
  delimiter?: string;
  has_header?: boolean;
  header_leading_rows?: number;
}

export interface BatchUnitResult {
  unit_id: string;
  source_paths?: string[];
  target_paths?: string[];
  status: string;
  error?: string | null;
  result?: ValidateResult | null;
}

export interface BatchValidateResponse {
  summary: {
    total_units: number;
    completed_units: number;
    failed_units: number;
    skipped_units: number;
    passed_units: number;
    is_match: boolean;
  };
  units: BatchUnitResult[];
  on_unit_failure?: string;
}

export interface ValidationMismatchesResponse {
  run_id: string;
  items: MismatchSampleRow[];
  total: number;
  offset: number;
  limit: number;
}

export interface ValidationHistorySummary {
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
  mapping_count: number;
  durations?: { upload_seconds?: number; validation_seconds?: number; total_seconds?: number };
  created_at: string;
  completed_at?: string | null;
  source_row_count?: number | null;
  target_row_count?: number | null;
  test_mode?: 'litmus' | 'full' | null;
}

export interface ValidationHistoryDetail extends ValidationHistorySummary {
  column_mappings?: ColumnMapping[];
  compared_column_count: number | null;
  compared_columns: string[];
}

export interface ValidationHistoryListResponse {
  items: ValidationHistorySummary[];
  total: number;
  file_pair_key?: string | null;
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
  validateLocalBatch: '/validate/local/batch',
  validateLocalColumns: '/validate/local/columns',
  validateOptions: '/validate/options',
  validateLocalFixedWidthLayout: '/validate/local/fixed-width-layout',
  validateLocalJsonParentPreview: '/validate/local/json-parent-preview',
  validateCloudBrowse: '/validate/cloud/browse',
  validateCloudProfile: '/validate/cloud/profile',
  cloudConnections: '/admin/cloud-connections',
  validateJob: (jobId: string) => `/validate/jobs/${jobId}`,
  validateJobMismatches: (jobId: string) => `/validate/jobs/${jobId}/mismatches`,
  validateDailyStats: '/validate/history/daily-stats',
  validateEntityInsights: '/validate/history/entities/insights',
  validateCreateEntity: '/validate/history/entities',
  validateHistoryDraft: '/validate/history/draft',
  validateHistory: '/validate/history',
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

  /** POST /admin/cloud-connections — create a saved GCS connection profile */
  createCloudConnection: (body: CloudConnectionCreateRequest): Promise<AxiosResponse<CloudConnection>> =>
    httpClient.post(E.cloudConnections, body),

  /** PATCH /admin/cloud-connections/{id} — update a saved connection */
  updateCloudConnection: (
    connectionId: string,
    body: CloudConnectionUpdateRequest,
  ): Promise<AxiosResponse<CloudConnection>> =>
    httpClient.patch(`${E.cloudConnections}/${connectionId}`, body),

  /** DELETE /admin/cloud-connections/{id} */
  deleteCloudConnection: (connectionId: string): Promise<AxiosResponse<void>> =>
    httpClient.delete(`${E.cloudConnections}/${connectionId}`),

  /** POST /validate/cloud/browse — list GCS prefixes/objects under a bucket prefix */
  browseCloud: (body: CloudBrowseRequest): Promise<AxiosResponse<CloudBrowseResponse>> =>
    httpClient.post(E.validateCloudBrowse, body),

  /** POST /validate/cloud/profile — detect format and row/column counts for one GCS object */
  profileCloudFile: (body: CloudFileProfileRequest): Promise<AxiosResponse<CloudFileProfileResponse>> =>
    httpClient.post(E.validateCloudProfile, body),

  /** POST /validate/local/columns — header preview (supports source_cloud / target_cloud) */
  previewValidationColumns: (body: ValidateRequest): Promise<AxiosResponse<LocalColumnPreviewResponse>> =>
    httpClient.post(E.validateLocalColumns, body),

  /** GET /validate/options — wizard test modes and snippet limits */
  getValidationOptions: (): Promise<AxiosResponse<ValidationOptionsResponse>> =>
    httpClient.get(E.validateOptions),

  /** POST /validate/local/fixed-width-layout — infer slices and date formats */
  previewFixedWidthLayout: (body: ValidateRequest): Promise<AxiosResponse<FixedWidthLayoutPreviewResponse>> =>
    httpClient.post(E.validateLocalFixedWidthLayout, body),

  previewJsonParentMapping: (body: ValidateRequest): Promise<AxiosResponse<JsonParentPreviewResponse>> =>
    httpClient.post(E.validateLocalJsonParentPreview, body),

  /** POST /validate/local — queue validation job (202); use source_cloud + target_cloud for GCS */
  submitValidation: (body: ValidateRequest): Promise<AxiosResponse<ValidationJobAcceptedResponse>> =>
    httpClient.post(E.validateLocal, body),

  /** POST /validate/local/batch — queue multi-pair batch validation */
  submitBatchValidation: (
    body: BatchValidateRequest,
  ): Promise<AxiosResponse<ValidationJobAcceptedResponse>> =>
    httpClient.post(E.validateLocalBatch, body),

  /** GET /validate/jobs/{job_id} — poll job status/result */
  getValidationJob: (
    jobId: string,
    options: { summaryOnly?: boolean } = {},
  ): Promise<AxiosResponse<ValidationJobDetailResponse>> =>
    httpClient.get(E.validateJob(jobId), {
      params: options.summaryOnly ? { summary_only: true } : undefined,
      timeout: JOB_POLL_TIMEOUT_MS,
    }),

  /** GET /validate/jobs/{job_id}/mismatches — paginated rows from on-disk job artifact */
  getValidationJobMismatches: (
    jobId: string,
    params: { limit: number; offset: number; mismatch_type?: string },
  ): Promise<AxiosResponse<ValidationMismatchesResponse>> =>
    httpClient.get(E.validateJobMismatches(jobId), { params }),

  /** Poll until completed or failed; retries transient network/gateway errors. */
  pollValidationUntilComplete: async (jobId: string): Promise<ValidateResult> => {
    let backoffMs = POLL_INTERVAL_MS;
    for (;;) {
      try {
        const { data } = await Api.getValidationJob(jobId, { summaryOnly: true });
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

  /** GET /validate/history — paginated validation or mapping history */
  listValidationHistory: (params: {
    limit?: number;
    offset?: number;
    kind?: 'validation' | 'mapping';
    source_path?: string;
    target_path?: string;
  } = {}): Promise<AxiosResponse<ValidationHistoryListResponse>> =>
    httpClient.get(E.validateHistory, { params }),

  /** DELETE /validate/history/{run_id} — remove one persisted run */
  deleteValidationHistoryRun: (runId: string): Promise<AxiosResponse<void>> =>
    httpClient.delete(E.validateHistoryRun(runId)),

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
  saveValidationDraft: (body: SaveDraftRequest): Promise<AxiosResponse<ValidationHistoryDetail>> =>
    httpClient.post(E.validateHistoryDraft, body),
};