export type {
  ColumnMapping,
  ValidateLocalRequest,
  LocalBrowseEntry,
  LocalBrowseResponse,
  FileDetectionResponse,
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
  sourcePath: string | null;
  targetPath: string | null;
  sourceFileName: string | null;
  targetFileName: string | null;
  uidColumn: string;
  delimiter: string;
  columnMappings: import('../../shared/api/Api').ColumnMapping[];
}

export interface ValidationReducerState {
  currentStep: number;
  isStep1Valid: boolean;
  validationForm: ValidationFormState;
  validationDataState: {
    data: ValidationDataResponse | null;
    isFetching: boolean;
    error: string | null;
  };
}
