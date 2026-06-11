/**
 * Central API client for Pegasus dashboard + validation features.
 * Base URL: `${VITE_API_BASE}/api/v1` (empty VITE_API_BASE → same-origin /api via nginx).
 */
import { type AxiosResponse } from 'axios';

import { httpClient } from './httpClient';

// ─── Request / response types ───────────────────────────────────────────────

export interface ColumnMapping {
  source_column: string;
  target_column: string;
  target_columns?: string[];
}

export interface ValidateLocalRequest {
  source_path: string;
  target_path: string;
  uid_column?: string;
  delimiter?: string;
  column_mappings?: ColumnMapping[];
  has_header?: boolean;
  file_format?: string;
}

export interface LocalBrowseEntry {
  name: string;
  path: string;
  is_dir: boolean;
}

export interface LocalBrowseResponse {
  path: string;
  parent_path: string | null;
  entries: LocalBrowseEntry[];
  truncated?: boolean;
}

export interface LocalBrowseConfigResponse {
  default_browse_path: string;
  path_remap_enabled: boolean;
  host_path_prefix: string | null;
  container_path_prefix: string | null;
}

export interface FileDetectionResponse {
  path: string;
  file_size_bytes: number;
  suggested_file_format: string | null;
  dataset_model: string;
  schema?: { metadata?: Record<string, unknown> };
}

export interface LocalColumnPreviewResponse {
  source_columns: string[];
  target_columns: string[];
  compare_columns: string[];
  auto_mappings: Array<{ source_column: string; target_column: string }>;
  unmatched_source_columns: string[];
  unmatched_target_columns: string[];
  delimiter: string;
  source_samples: Record<string, string[]>;
  target_samples: Record<string, string[]>;
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
  validateLocalBrowse: '/validate/local/browse',
  validateLocalBrowseConfig: '/validate/local/browse/config',
  validateLocalDetect: '/validate/local/detect',
  validateLocalColumns: '/validate/local/columns',
  validateJob: (jobId: string) => `/validate/jobs/${jobId}`,
  validateDailyStats: '/validate/history/daily-stats',
  validateEntityInsights: '/validate/history/entities/insights',
  validateCreateEntity: '/validate/history/entities',
  validateHistoryDraft: '/validate/history/draft',
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

  /** GET /validate/local/browse/config — default browse directory */
  getLocalBrowseConfig: (): Promise<AxiosResponse<LocalBrowseConfigResponse>> =>
    httpClient.get(E.validateLocalBrowseConfig),

  /** GET /validate/local/browse?path= — list server files/folders */
  browseLocal: (path?: string): Promise<AxiosResponse<LocalBrowseResponse>> =>
    httpClient.get(E.validateLocalBrowse, { params: path ? { path } : undefined }),

  /** GET /validate/local/detect?path= — file format/size overview (step 2) */
  detectLocalFile: (path: string): Promise<AxiosResponse<FileDetectionResponse>> =>
    httpClient.get(E.validateLocalDetect, { params: { path } }),

  /** GET /validate/local/columns — header preview + auto-mappings (step 3) */
  previewLocalColumns: (params: {
    source_path: string;
    target_path: string;
    uid_column?: string;
    delimiter?: string;
  }): Promise<AxiosResponse<LocalColumnPreviewResponse>> =>
    httpClient.get(E.validateLocalColumns, { params }),

  /** POST /validate/local — queue validation job (202) */
  submitValidation: (body: ValidateLocalRequest): Promise<AxiosResponse<ValidationJobAcceptedResponse>> =>
    httpClient.post(E.validateLocal, body),

  /** GET /validate/jobs/{job_id} — poll job status/result */
  getValidationJob: (jobId: string): Promise<AxiosResponse<ValidationJobDetailResponse>> =>
    httpClient.get(E.validateJob(jobId)),

  /** Poll until completed or failed */
  pollValidationUntilComplete: async (jobId: string): Promise<ValidateResult> => {
    for (;;) {
      const { data } = await Api.getValidationJob(jobId);
      if (data.status === 'completed' && data.result) return data.result;
      if (data.status === 'failed') throw new Error(data.error || 'Validation failed');
      await new Promise((r) => setTimeout(r, 2000));
    }
  },

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
