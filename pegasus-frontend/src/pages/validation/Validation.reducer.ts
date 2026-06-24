import { type PayloadAction, createSlice } from '@reduxjs/toolkit';
import { initializeNullState } from '../../shared/constants/common.constant';
import {
  type OverviewProfileCache,
  type ValidationFormState,
  type ValidationReducerState,
  type ValidationDataResponse,
} from './Validation.interface';
import type { GoogleCloudStorageConfig } from '../../shared/api/Api';
import type { ValidationTabSession } from './validationTabStorage';

const cloudObjectKey = (cloud: GoogleCloudStorageConfig | null): string =>
  cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '';

const shouldClearOverviewCache = (
  prev: ValidationFormState,
  patch: Partial<ValidationFormState>,
): boolean => {
  if (patch.sourceCloud !== undefined && cloudObjectKey(patch.sourceCloud ?? null) !== cloudObjectKey(prev.sourceCloud)) {
    return true;
  }
  if (patch.targetCloud !== undefined && cloudObjectKey(patch.targetCloud ?? null) !== cloudObjectKey(prev.targetCloud)) {
    return true;
  }
  if (patch.hasHeader !== undefined && patch.hasHeader !== prev.hasHeader) {
    return true;
  }
  return false;
};

const shouldResetFixedWidthLayout = (
  prev: ValidationFormState,
  patch: Partial<ValidationFormState>,
): boolean => {
  if (patch.sourceCloud !== undefined && cloudObjectKey(patch.sourceCloud ?? null) !== cloudObjectKey(prev.sourceCloud)) {
    return true;
  }
  if (patch.targetCloud !== undefined && cloudObjectKey(patch.targetCloud ?? null) !== cloudObjectKey(prev.targetCloud)) {
    return true;
  }
  return false;
};

const defaultValidationForm: ValidationFormState = {
  connectionId: null,
  bucket: null,
  browsePrefix: '',
  sourceCloud: null,
  targetCloud: null,
  sourceFileName: null,
  targetFileName: null,
  sourceFileSize: null,
  targetFileSize: null,
  uidColumn: 'id',
  delimiter: 'auto',
  hasHeader: true,
  structuredOrderSensitive: false,
  columnMappings: [],
  detectedFileFormat: null,
  fixedWidthColumns: [],
  fixedWidthLineWidth: null,
  testMode: 'full',
  mismatchSnippetLimit: null,
};

export const initialState: ValidationReducerState = {
  currentStep: 1,
  isStep1Valid: false,
  wizardRunId: null,
  validationForm: defaultValidationForm,
  overviewProfileCache: null,
  validationDataState: initializeNullState,
  pendingHistoryNavigation: null,
};

const validationSlice = createSlice({
  name: 'validation',
  initialState,
  reducers: {
    setWizardStep: (state, action: PayloadAction<number>) => ({
      ...state,
      currentStep: action.payload,
    }),
    // ⚡ Action to toggle step eligibility
    setStep1Valid: (state, action: PayloadAction<boolean>) => ({
      ...state,
      isStep1Valid: action.payload,
    }),
    setValidationForm: (state, action: PayloadAction<Partial<ValidationFormState>>) => {
      const resetFixedWidth = shouldResetFixedWidthLayout(state.validationForm, action.payload);
      const clearedFixedWidth = resetFixedWidth && action.payload.fixedWidthColumns === undefined
        ? {
          fixedWidthColumns: [] as ValidationFormState['fixedWidthColumns'],
          fixedWidthLineWidth: null,
          detectedFileFormat: action.payload.detectedFileFormat ?? null,
        }
        : {};
      return {
        ...state,
        validationForm: { ...state.validationForm, ...action.payload, ...clearedFixedWidth },
        overviewProfileCache: shouldClearOverviewCache(state.validationForm, action.payload)
          ? null
          : state.overviewProfileCache,
      };
    },
    setOverviewProfileCache: (state, action: PayloadAction<OverviewProfileCache>) => ({
      ...state,
      overviewProfileCache: action.payload,
    }),
    setWizardRunId: (state, action: PayloadAction<string | null>) => ({
      ...state,
      wizardRunId: action.payload,
    }),
    resetWizard: () => ({
      currentStep: 1,
      isStep1Valid: false,
      wizardRunId: null,
      validationForm: defaultValidationForm,
      overviewProfileCache: null,
      validationDataState: initializeNullState,
      pendingHistoryNavigation: null,
    }),
    restoreTabSession: (_state, action: PayloadAction<ValidationTabSession>) => ({
      currentStep: 1,
      isStep1Valid: action.payload.isStep1Valid,
      wizardRunId: action.payload.wizardRunId,
      validationForm: { ...defaultValidationForm, ...action.payload.validationForm },
      overviewProfileCache: action.payload.overviewProfileCache,
      validationDataState: initializeNullState,
      pendingHistoryNavigation: null,
    }),
    clearValidationRun: (state) => ({
      ...state,
      currentStep: 1,
      validationDataState: initializeNullState,
    }),

    submitValidationRequest: (state) => ({
      ...state,
      validationDataState: { ...initializeNullState, isFetching: true },
    }),
    submitValidationSuccess: (state, action: PayloadAction<ValidationDataResponse>) => ({
      ...state,
      validationDataState: { ...initializeNullState, data: action.payload },
    }),
    submitValidationError: (state, action: PayloadAction<string>) => ({
      ...state,
      validationDataState: { ...initializeNullState, error: action.payload },
    }),
    navigateToPairHistory: (
      state,
      action: PayloadAction<{ sourcePath: string; targetPath: string }>,
    ) => ({
      ...state,
      pendingHistoryNavigation: action.payload,
      validationDataState: { ...initializeNullState, isFetching: false },
    }),
    clearPendingHistoryNavigation: (state) => ({
      ...state,
      pendingHistoryNavigation: null,
    }),
    runValidationFromHistoryRequest: (state, _action: PayloadAction<string>) => ({
      ...state,
      validationDataState: { ...initializeNullState, isFetching: true },
    }),
  },
});

export const validationActions = { ...validationSlice.actions };
export default validationSlice.reducer;