import { AxiosError, AxiosHeaders } from 'axios'

import { initializeNullState } from '~/shared/constants/common.constants'
import type {
  CloudBrowseResponse,
  CloudConnection,
  CloudFileProfileResponse,
  GoogleCloudStorageConfig,
  ValidationHistoryDetail,
} from '~/shared/api/Api'

import { ValidationDataResponse } from './Validation.interface'
import { initialState } from './Validation.reducer'

export const mockSourceCloud: GoogleCloudStorageConfig = {
  provider: 'google-cloud-storage',
  bucket: 'test-bucket',
  object_name: 'data/source.csv',
  connection_id: 'conn-1',
}

export const mockTargetCloud: GoogleCloudStorageConfig = {
  provider: 'google-cloud-storage',
  bucket: 'test-bucket',
  object_name: 'data/target.csv',
  connection_id: 'conn-1',
}

export const mockCloudConnection: CloudConnection = {
  id: 'conn-1',
  name: 'Test GCS',
  provider: 'google-cloud-storage',
  bucket: 'test-bucket',
  project_id: 'proj-1',
  active: true,
}

export const mockBrowseResponse: CloudBrowseResponse = {
  bucket: 'test-bucket',
  prefix: '',
  parent_prefix: null,
  entries: [
    {
      path: 'data/source.csv',
      name: 'source.csv',
      is_dir: false,
      size_bytes: 1024,
      updated_at: '2026-06-12T10:00:00.000Z',
    },
  ],
}

export const mockValidationResult: ValidationDataResponse = {
  jobId: 'job-123',
  runId: 'run-123',
  status: 'Complete',
  results: {
    summary: {
      source_row_count: 100,
      target_row_count: 100,
      total_mismatch_records: 0,
      is_match: true,
    },
    run_id: 'run-123',
    mismatch_counts: { missing_in_target: 0, extra_in_target: 0, value_mismatch: 0 },
    mismatch_sample_groups: {
      missing_in_target: [],
      extra_in_target: [],
      value_mismatch: [],
    },
  },
}

export const mockHistoryDetail: ValidationHistoryDetail = {
  run_id: 'run-draft-1',
  status: 'pending',
  source_path: 'gs://test-bucket/data/source.csv',
  target_path: 'gs://test-bucket/data/target.csv',
  source_filename: 'source.csv',
  target_filename: 'target.csv',
  uid_column: 'id',
  delimiter: 'auto',
  is_match: null,
  mismatch_counts: { missing_in_target: 0, extra_in_target: 0, value_mismatch: 0 },
  mapping_count: 2,
  created_at: '2026-06-12T10:00:00.000Z',
  column_mappings: [{ source_column: 'id', target_column: 'id' }],
  compared_column_count: 1,
  compared_columns: ['id'],
}

export const mockSaveDraftPayload = {
  draft: {
    source_path: 'gs://test-bucket/data/source.csv',
    target_path: 'gs://test-bucket/data/target.csv',
    uid_column: 'id',
    delimiter: 'auto',
    column_mappings: [{ source_column: 'id', target_column: 'id' }],
  },
  intent: 'save' as const,
}

export const mockAxiosError = new AxiosError(
  'Server error',
  'ERR_BAD_REQUEST',
  undefined,
  undefined,
  {
    status: 500,
    statusText: 'Internal Server Error',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: { message: 'Failed to load cloud connections' },
  },
)

export const validationFormWithFiles = {
  ...initialState.validationForm,
  sourceCloud: mockSourceCloud,
  targetCloud: mockTargetCloud,
  sourceFileName: 'source.csv',
  targetFileName: 'target.csv',
}

export const cloudConnectionsLoading = {
  ...initializeNullState,
  isFetching: true,
  error: null,
}

export const cloudConnectionsSuccess = {
  ...initializeNullState,
  data: [mockCloudConnection],
  isFetching: false,
  error: null,
}

export const cloudConnectionsError = {
  ...initializeNullState,
  isFetching: false,
  error: 'Failed to load cloud connections',
}

export const submitValidationLoading = {
  ...initializeNullState,
  isFetching: true,
  error: null,
}

export const submitValidationSuccess = {
  ...initializeNullState,
  data: mockValidationResult,
  isFetching: false,
  error: null,
}

export const validationStateStep1Ready = {
  ...initialState,
  isStep1Valid: true,
  validationForm: {
    ...initialState.validationForm,
    sourceCloud: mockSourceCloud,
    targetCloud: mockTargetCloud,
    sourceFileName: 'source.csv',
    targetFileName: 'target.csv',
  },
  cloudConnectionsState: cloudConnectionsSuccess,
}

export const validationStateWithConnections = {
  ...initialState,
  cloudConnectionsState: cloudConnectionsSuccess,
}

const overviewSourceKey = 'conn-1:test-bucket:data/source.csv'
const overviewTargetKey = 'conn-1:test-bucket:data/target.csv'

export const mockSourceProfile: CloudFileProfileResponse = {
  object_name: 'data/source.csv',
  gcs_uri: 'gs://test-bucket/data/source.csv',
  file_size_bytes: 1024,
  file_format: 'csv',
  suggested_file_format: 'csv',
  column_count: 5,
  row_count: 100,
  delimiter: ',',
  has_header: true,
}

export const mockTargetProfile: CloudFileProfileResponse = {
  object_name: 'data/target.csv',
  gcs_uri: 'gs://test-bucket/data/target.csv',
  file_size_bytes: 1024,
  file_format: 'csv',
  suggested_file_format: 'csv',
  column_count: 5,
  row_count: 100,
  delimiter: ',',
  has_header: true,
}

export const overviewProfileCacheSuccess = {
  sourceKey: overviewSourceKey,
  targetKey: overviewTargetKey,
  source: mockSourceProfile,
  target: mockTargetProfile,
  sourceError: false,
  targetError: false,
}

export const validationStateStep2Ready = {
  ...validationStateStep1Ready,
  currentStep: 2,
  overviewProfileCache: overviewProfileCacheSuccess,
  validationForm: {
    ...validationStateStep1Ready.validationForm,
    sourceFileSize: 1024,
    targetFileSize: 1024,
    uidColumn: 'id',
    delimiter: 'auto',
    hasHeader: true,
    detectedFileFormat: 'csv',
  },
}

export const validationStateStep3Ready = {
  ...validationStateStep2Ready,
  currentStep: 3,
  validationForm: {
    ...validationStateStep2Ready.validationForm,
    columnMappings: [
      { source_column: 'id', target_column: 'id' },
      { source_column: 'name', target_column: 'name' },
    ],
  },
  previewColumnsState: {
    pairKey: `${overviewSourceKey}|${overviewTargetKey}|id|auto|true`,
    data: {
      source_columns: ['id', 'name'],
      target_columns: ['id', 'name'],
      compare_columns: ['id', 'name'],
      auto_mappings: [
        { source_column: 'id', target_column: 'id' },
        { source_column: 'name', target_column: 'name' },
      ],
      unmatched_source_columns: [],
      unmatched_target_columns: [],
      delimiter: ',',
      has_header: true,
      source_samples: { id: ['1'], name: ['alpha'] },
      target_samples: { id: ['1'], name: ['alpha'] },
      sample_row_count: 1,
    },
    isFetching: false,
    error: null,
  },
}
