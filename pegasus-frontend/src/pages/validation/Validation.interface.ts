export type {
  ColumnMapping,
  ValidateRequest,
  GoogleCloudStorageConfig,
  CloudBrowseEntry,
  CloudBrowseResponse,
  CloudConnection,
  LocalColumnPreviewResponse,
  MismatchCounts,
  MismatchSampleRow,
  ValidateResult,
  ValidationJobDetailResponse,
  ValidationMismatchesResponse,
} from '../../shared/api/Api';

export interface ValidationDataResponse {
  jobId: string | null;
  runId: string | null;
  status: 'Pending' | 'Uploading' | 'Validating' | 'Complete' | 'Failed';
  results: import('../../shared/api/Api').ValidateResult | null;
}

export interface ValidationFormState {
  connectionId: string | null;
  bucket: string | null;
  browsePrefix: string;
  sourceCloud: import('../../shared/api/Api').GoogleCloudStorageConfig | null;
  targetCloud: import('../../shared/api/Api').GoogleCloudStorageConfig | null;
  sourceFileName: string | null;
  targetFileName: string | null;
  sourceFileSize: number | null;
  targetFileSize: number | null;
  uidColumn: string;
  delimiter: string;
  hasHeader: boolean;
  structuredOrderSensitive: boolean;
  columnMappings: import('../../shared/api/Api').ColumnMapping[];
}

/** Cached GCS file profiles for step 2; cleared when source/target objects change. */
export interface OverviewProfileCache {
  sourceKey: string;
  targetKey: string;
  source: import('../../shared/api/Api').CloudFileProfileResponse | null;
  target: import('../../shared/api/Api').CloudFileProfileResponse | null;
  sourceError: boolean;
  targetError: boolean;
}

export interface ValidationReducerState {
  currentStep: number;
  isStep1Valid: boolean;
  wizardRunId: string | null;
  validationForm: ValidationFormState;
  overviewProfileCache: OverviewProfileCache | null;
  validationDataState: {
    data: ValidationDataResponse | null;
    isFetching: boolean;
    error: string | null;
  };
  /** Navigate to execution history for this file pair after validation starts or completes. */
  pendingHistoryNavigation: { sourcePath: string; targetPath: string } | null;
}
