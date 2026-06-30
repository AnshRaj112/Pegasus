import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import { initializeNullState } from '~/shared/constants/common.constants';
import {
 OverviewProfileCache,
 ValidationFormState,
 ValidationReducerState,
 ValidationDataResponse,
 BrowseCloudRequestPayload,
 ProfileCloudFilesRequestPayload,
 SaveDraftIntent,
} from './Validation.interface';
import { GoogleCloudStorageConfig, LocalColumnPreviewResponse, FixedWidthLayoutPreviewResponse, SaveDraftRequest, ValidationHistoryDetail } from '../../shared/api/Api';
import { ValidationTabSession } from './validationTabStorage';

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
  if (patch.delimiter !== undefined && patch.delimiter !== prev.delimiter) {
    return true;
  }
  if (patch.hasHeader !== undefined && patch.hasHeader !== prev.hasHeader) {
    return true;
  }
  return false;
};

const shouldClearPreviewCache = (
  prev: ValidationFormState,
  patch: Partial<ValidationFormState>,
): boolean => {
  if (patch.uidColumn !== undefined && patch.uidColumn !== prev.uidColumn) {
    return true;
  }
  if (patch.delimiter !== undefined && patch.delimiter !== prev.delimiter) {
    return true;
  }
  if (patch.hasHeader !== undefined && patch.hasHeader !== prev.hasHeader) {
    return true;
  }
  return false;
};

const shouldClearColumnMappings = (
  prev: ValidationFormState,
  patch: Partial<ValidationFormState>,
): boolean => {
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
};

export const initialState: ValidationReducerState = {
  currentStep: 1,
  isStep1Valid: false,
  wizardRunId: null,
  validationForm: defaultValidationForm,
  overviewProfileCache: null,
  overviewProfileFetchState: {
    sourceKey: null,
    targetKey: null,
    isFetching: false,
  },
  validationDataState: initializeNullState,
  pendingHistoryNavigation: null,
  cloudConnectionsState: initializeNullState,
  browseCloudState: {
    pathId: null,
    connectionId: null,
    background: false,
    isFetching: false,
    data: null,
    error: null,
  },
  previewColumnsState: {
    pairKey: null,
    data: null,
    isFetching: false,
    error: null,
  },
  previewFixedWidthState: {
    pairKey: null,
    data: null,
    isFetching: false,
    error: null,
  },
  saveDraftState: {
    data: null,
    intent: null,
    isFetching: false,
    error: null,
  },
  overviewPreviewShown: false,
  overviewPreviewSessionKey: null,
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
        }
        : {};
      const clearedMappings = shouldClearColumnMappings(state.validationForm, action.payload)
        && action.payload.columnMappings === undefined
        ? { columnMappings: [] as ValidationFormState['columnMappings'] }
        : {};
      return {
        ...state,
        validationForm: {
          ...state.validationForm,
          ...action.payload,
          ...clearedFixedWidth,
          ...clearedMappings,
        },
        overviewProfileCache: shouldClearOverviewCache(state.validationForm, action.payload)
          ? null
          : state.overviewProfileCache,
        overviewPreviewShown: shouldClearOverviewCache(state.validationForm, action.payload)
          ? false
          : state.overviewPreviewShown,
        overviewPreviewSessionKey: shouldClearOverviewCache(state.validationForm, action.payload)
          ? null
          : state.overviewPreviewSessionKey,
        overviewProfileFetchState: shouldClearOverviewCache(state.validationForm, action.payload)
          ? initialState.overviewProfileFetchState
          : state.overviewProfileFetchState,
        previewColumnsState: shouldClearPreviewCache(state.validationForm, action.payload)
          || shouldClearOverviewCache(state.validationForm, action.payload)
          ? initialState.previewColumnsState
          : state.previewColumnsState,
        previewFixedWidthState: shouldClearPreviewCache(state.validationForm, action.payload)
          || shouldResetFixedWidthLayout(state.validationForm, action.payload)
          ? initialState.previewFixedWidthState
          : state.previewFixedWidthState,
      };
    },
    setOverviewProfileCache: (state, action: PayloadAction<OverviewProfileCache>) => ({
      ...state,
      overviewProfileCache: action.payload,
      overviewProfileFetchState: {
        sourceKey: action.payload.sourceKey,
        targetKey: action.payload.targetKey,
        isFetching: false,
      },
      overviewPreviewShown: false,
      overviewPreviewSessionKey: null,
    }),
    retryOverviewProfiles: (state) => ({
      ...state,
      overviewProfileCache: null,
      overviewProfileFetchState: initialState.overviewProfileFetchState,
      overviewPreviewShown: false,
      overviewPreviewSessionKey: null,
      previewColumnsState: initialState.previewColumnsState,
      previewFixedWidthState: initialState.previewFixedWidthState,
    }),
    setOverviewPreviewShown: (state, action: PayloadAction<{ sessionKey: string }>) => ({
      ...state,
      overviewPreviewShown: true,
      overviewPreviewSessionKey: action.payload.sessionKey,
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
      overviewProfileFetchState: initialState.overviewProfileFetchState,
      validationDataState: initializeNullState,
      pendingHistoryNavigation: null,
      cloudConnectionsState: initializeNullState,
      browseCloudState: initialState.browseCloudState,
      previewColumnsState: initialState.previewColumnsState,
      previewFixedWidthState: initialState.previewFixedWidthState,
      saveDraftState: initialState.saveDraftState,
      overviewPreviewShown: false,
      overviewPreviewSessionKey: null,
    }),
    restoreTabSession: (_state, action: PayloadAction<ValidationTabSession>) => ({
      currentStep: 1,
      isStep1Valid: action.payload.isStep1Valid,
      wizardRunId: action.payload.wizardRunId,
      validationForm: { ...defaultValidationForm, ...action.payload.validationForm },
      overviewProfileCache: action.payload.overviewProfileCache,
      overviewProfileFetchState: initialState.overviewProfileFetchState,
      validationDataState: initializeNullState,
      pendingHistoryNavigation: null,
      cloudConnectionsState: initializeNullState,
      browseCloudState: initialState.browseCloudState,
      previewColumnsState: initialState.previewColumnsState,
      previewFixedWidthState: initialState.previewFixedWidthState,
      saveDraftState: initialState.saveDraftState,
      overviewPreviewShown: false,
      overviewPreviewSessionKey: null,
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

    listCloudConnectionsRequest: (state) => ({
      ...state,
      cloudConnectionsState: { ...initializeNullState, isFetching: true },
    }),
    listCloudConnectionsSuccess: (state, action: PayloadAction<import('../../shared/api/Api').CloudConnection[]>) => ({
      ...state,
      cloudConnectionsState: { ...initializeNullState, data: action.payload },
    }),
    listCloudConnectionsError: (state, action: PayloadAction<string>) => ({
      ...state,
      cloudConnectionsState: { ...initializeNullState, error: action.payload },
    }),

    browseCloudRequest: (state, action: PayloadAction<BrowseCloudRequestPayload>) => ({
      ...state,
      browseCloudState: {
        pathId: action.payload.pathId,
        connectionId: action.payload.connectionId,
        background: Boolean(action.payload.background),
        isFetching: !action.payload.background,
        data: null,
        error: null,
      },
    }),
    browseCloudSuccess: (state, action: PayloadAction<{
      pathId: string;
      connectionId: string;
      data: import('../../shared/api/Api').CloudBrowseResponse;
    }>) => ({
      ...state,
      browseCloudState: {
        ...state.browseCloudState,
        pathId: action.payload.pathId,
        connectionId: action.payload.connectionId,
        isFetching: false,
        data: action.payload.data,
        error: null,
      },
    }),
    browseCloudError: (state, action: PayloadAction<{ pathId: string; error: string }>) => ({
      ...state,
      browseCloudState: {
        ...state.browseCloudState,
        pathId: action.payload.pathId,
        isFetching: false,
        data: null,
        error: action.payload.error,
      },
    }),

    profileCloudFilesRequest: (state, action: PayloadAction<ProfileCloudFilesRequestPayload>) => ({
      ...state,
      overviewProfileFetchState: {
        sourceKey: action.payload.sourceKey,
        targetKey: action.payload.targetKey,
        isFetching: true,
      },
    }),

    previewValidationColumnsRequest: (state, action: PayloadAction<string>) => {
      if (
        state.previewColumnsState.pairKey === action.payload
        && (state.previewColumnsState.isFetching || state.previewColumnsState.data)
      ) {
        return state;
      }
      return {
        ...state,
        overviewPreviewShown: false,
        overviewPreviewSessionKey: null,
        previewColumnsState: {
          pairKey: action.payload,
          data: null,
          isFetching: true,
          error: null,
        },
      };
    },
    previewValidationColumnsSuccess: (state, action: PayloadAction<{
      pairKey: string;
      data: LocalColumnPreviewResponse;
    }>) => ({
      ...state,
      previewColumnsState: {
        pairKey: action.payload.pairKey,
        data: action.payload.data,
        isFetching: false,
        error: null,
      },
    }),
    previewValidationColumnsError: (state, action: PayloadAction<{ pairKey: string; error: string }>) => ({
      ...state,
      previewColumnsState: {
        pairKey: action.payload.pairKey,
        data: null,
        isFetching: false,
        error: action.payload.error,
      },
    }),

    previewFixedWidthLayoutRequest: (state, action: PayloadAction<string>) => {
      if (
        state.previewFixedWidthState.pairKey === action.payload
        && (state.previewFixedWidthState.isFetching || state.previewFixedWidthState.data)
      ) {
        return state;
      }
      return {
        ...state,
        overviewPreviewShown: false,
        overviewPreviewSessionKey: null,
        previewFixedWidthState: {
          pairKey: action.payload,
          data: null,
          isFetching: true,
          error: null,
        },
      };
    },
    previewFixedWidthLayoutSuccess: (state, action: PayloadAction<{
      pairKey: string;
      data: FixedWidthLayoutPreviewResponse;
    }>) => ({
      ...state,
      previewFixedWidthState: {
        pairKey: action.payload.pairKey,
        data: action.payload.data,
        isFetching: false,
        error: null,
      },
    }),
    previewFixedWidthLayoutError: (state, action: PayloadAction<{ pairKey: string; error: string }>) => ({
      ...state,
      previewFixedWidthState: {
        pairKey: action.payload.pairKey,
        data: null,
        isFetching: false,
        error: action.payload.error,
      },
    }),

    saveDraftRequest: (state, action: PayloadAction<{ draft: SaveDraftRequest; intent: SaveDraftIntent }>) => ({
      ...state,
      saveDraftState: {
        data: null,
        intent: action.payload.intent,
        isFetching: true,
        error: null,
      },
    }),
    saveDraftSuccess: (state, action: PayloadAction<ValidationHistoryDetail>) => ({
      ...state,
      wizardRunId: action.payload.run_id,
      saveDraftState: {
        data: action.payload,
        intent: state.saveDraftState.intent,
        isFetching: false,
        error: null,
      },
    }),
    saveDraftError: (state, action: PayloadAction<string>) => ({
      ...state,
      saveDraftState: {
        data: null,
        intent: state.saveDraftState.intent,
        isFetching: false,
        error: action.payload,
      },
    }),
    clearSaveDraftState: (state) => ({
      ...state,
      saveDraftState: initialState.saveDraftState,
    }),
  },
});

export const validationActions = { ...validationSlice.actions };
export default validationSlice.reducer;