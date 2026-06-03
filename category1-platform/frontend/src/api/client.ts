import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export interface JobSummary {
  job_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  progress_pct: number;
  current_phase: string;
}

export interface ReconciliationResult {
  job_id: string;
  status: string;
  missing_count: number;
  extra_count: number;
  mismatched_count: number;
  matching_count: number;
  source_row_count?: number;
  target_row_count?: number;
  schema_validation?: {
    is_valid: boolean;
    differences: Array<{
      column: string;
      difference_type: string;
      source_value?: string;
      target_value?: string;
    }>;
  };
  sample_mismatches?: Array<{
    record_key: string;
    partition_id: number;
    mismatch_type: string;
    column_differences?: Array<{
      column: string;
      source_value?: string;
      target_value?: string;
    }>;
  }>;
  execution_stats?: {
    duration_seconds: number;
    source_rows_processed: number;
    target_rows_processed: number;
    partitions_processed: number;
    peak_memory_mb: number;
    disk_spill_mb: number;
    chunks_processed: number;
  };
  error_message?: string;
}

export interface Defaults {
  chunk_sizes: number[];
  partition_counts: number[];
  file_formats: string[];
  source_types: string[];
  key_strategies: string[];
}

export async function getHealth() {
  const { data } = await api.get('/health');
  return data;
}

export async function getDefaults(): Promise<Defaults> {
  const { data } = await api.get('/config/defaults');
  return data;
}

export async function listJobs(): Promise<JobSummary[]> {
  const { data } = await api.get('/jobs');
  return data;
}

export async function getJob(jobId: string): Promise<ReconciliationResult> {
  const { data } = await api.get(`/jobs/${jobId}`);
  return data;
}

export async function getJobSummary(jobId: string): Promise<JobSummary> {
  const { data } = await api.get(`/jobs/${jobId}/summary`);
  return data;
}

export async function createJobWithUpload(formData: FormData): Promise<JobSummary> {
  const { data } = await api.post('/jobs/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function deleteJob(jobId: string) {
  const { data } = await api.delete(`/jobs/${jobId}`);
  return data;
}

export function getReportUrl(jobId: string): string {
  return `/api/jobs/${jobId}/report`;
}
