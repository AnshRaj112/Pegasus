export type {
  ColumnMapping,
  ValidateRequest,
  GoogleCloudStorageConfig,
  CloudBrowseEntry,
  CloudBrowseResponse,
  CloudConnection,
  LocalColumnPreviewResponse,
  FixedWidthColumnPreview,
  FixedWidthConfig,
  FixedWidthLayoutPreviewResponse,
  MismatchCounts,
  MismatchSampleRow,
  ValidateResult,
  ValidationJobDetailResponse,
  ValidationMismatchesResponse,
  ValidationHistoryDetail,
  SaveDraftRequest,
} from '../../shared/api/Api';

export interface AsyncState<T> {
  data: T | null;
  isFetching: boolean;
  error: string | null;
}

export type SaveDraftIntent = 'proceed' | 'save';

export interface BrowseCloudRequestPayload {
  pathId: string;
  connectionId: string;
  bucket: string | null;
  prefix: string;
  background?: boolean;
}

export interface BrowseCloudState {
  pathId: string | null;
  connectionId: string | null;
  background: boolean;
  isFetching: boolean;
  data: import('../../shared/api/Api').CloudBrowseResponse | null;
  error: string | null;
}

export interface PreviewRequestState<T> {
  pairKey: string | null;
  data: T | null;
  isFetching: boolean;
  error: string | null;
}

export interface SaveDraftState {
  data: import('../../shared/api/Api').ValidationHistoryDetail | null;
  intent: SaveDraftIntent | null;
  isFetching: boolean;
  error: string | null;
}

export interface ProfileCloudFilesRequestPayload {
  sourceKey: string;
  targetKey: string;
}

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
  detectedFileFormat: string | null;
  fixedWidthColumns: import('../../shared/api/Api').FixedWidthColumnPreview[];
  fixedWidthLineWidth: number | null;
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
  cloudConnectionsState: AsyncState<import('../../shared/api/Api').CloudConnection[]>;
  browseCloudState: BrowseCloudState;
  previewColumnsState: PreviewRequestState<import('../../shared/api/Api').LocalColumnPreviewResponse>;
  previewFixedWidthState: PreviewRequestState<import('../../shared/api/Api').FixedWidthLayoutPreviewResponse>;
  saveDraftState: SaveDraftState;
}
