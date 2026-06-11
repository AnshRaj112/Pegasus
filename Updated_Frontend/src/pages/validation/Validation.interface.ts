export interface ValidationDataResponse {
  jobId: string | null;
  status: 'Pending' | 'Uploading' | 'Validating' | 'Complete' | 'Failed';
  results: any | null; // We can strongly type this later when we know the result shape
}

export interface ValidationReducerState {
  currentStep: number;
  isStep1Valid: boolean;
  validationDataState: {
    data: ValidationDataResponse | null;
    isFetching: boolean;
    error: string | null;
  };
}