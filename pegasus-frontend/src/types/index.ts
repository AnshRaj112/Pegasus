export interface MismatchCount {
  missing_in_target?: number
  extra_in_target?: number
  value_mismatch?: number
}

export interface Durations {
  upload_seconds?: number
  validation_seconds?: number
  total_seconds?: number
}

export interface ColumnMapping {
  source_column: string
  target_column: string
}

export interface ValidationRun {
  run_id: string
  created_at: string
  completed_at?: string
  status: string
  source_path: string
  source_filename?: string
  target_path: string
  target_filename?: string
  is_match?: boolean
  source_row_count?: number
  target_row_count?: number
  mismatch_counts?: MismatchCount
  durations?: Durations
  column_mappings?: ColumnMapping[]
  compared_columns?: string[]
  uid_column?: string
  delimiter?: string
}

export interface EntityInsight {
  display_name: string
  aliases: string[]
  validation_count: number
  pass_rate: number
  last_validation?: string
}

export interface Workspace {
  workspace_name: string
  created_at: string
  active_users: number
  status: 'active' | 'suspended'
}

export interface StoreBucket {
  bucket_name: string
  provider: 'gcs' | 's3' | 'local'
  connection_status: 'connected' | 'failed' | 'untested'
  bucket_path: string
  last_sync?: string
  region?: string
}

export interface ActiveTask {
  task_name: string
  status: 'completed' | 'running' | 'scheduled' | 'failed'
  progress: number
}

export interface MappingPair {
  source_column: string
  target_column: string
  data_type?: string
}

export interface UserProfile {
  username: string
  email: string
  role: 'super_user' | 'admin' | 'user'
  access_controls_enabled: boolean
  avatar_url?: string
}

export interface ChartDataPoint {
  timestamp: string
  value: number
  label?: string
}
