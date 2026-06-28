import { call, delay, fork, put, select, takeLatest, all } from 'redux-saga/effects';
import { notification } from 'antd';
import { AxiosError } from 'axios';
import { PayloadAction } from '@reduxjs/toolkit';

import { Api, ValidationJobAcceptedResponse } from '../../shared/api/Api';
import { getApiErrorMessage, isTransientPollError, pollRecoveryHint } from '../../shared/api/apiError';
import { NOTIFICATION_SERVICE_TYPES } from '~/shared/constants/common.constants';
import { reportActions } from '../report/Report.reducer';
import { gcsUri } from '../report/reportPairId';

import { ValidationDataResponse, ValidationReducerState } from './Validation.interface';
import { validationActions } from './Validation.reducer';
import { ValidationServiceApi } from './Validation.service';
import {
  removeActiveSession,
  upsertActiveSession,
} from './validationSessionStorage';
import { formFromHistory, enrichFormWithConnections, validateRequestFromForm } from './validationRerun';

const DEFER_TO_HISTORY_MS = 10_000;
const POLL_INTERVAL_MS = 2_000;

function* navigateToPairHistory(sourcePath: string, targetPath: string) {
  if (!sourcePath || !targetPath) return;
  yield put(validationActions.navigateToPairHistory({ sourcePath, targetPath }));
}

function* submitValidationSuccess(
  jobId: string,
  result: import('../../shared/api/Api').ValidateResult,
  sourcePath: string,
  targetPath: string,
) {
  removeActiveSession(jobId);
  const payload: ValidationDataResponse = {
    jobId,
    runId: result.run_id ?? null,
    status: 'Complete',
    results: result,
  };
  yield put(validationActions.submitValidationSuccess(payload));
  yield put(reportActions.fetchReportsRequest());
  yield* navigateToPairHistory(sourcePath, targetPath);
}

function* backgroundPollSaga(jobId: string, sourcePath: string, targetPath: string) {
  try {
    const result: import('../../shared/api/Api').ValidateResult = yield call(
      Api.pollValidationUntilComplete,
      jobId,
    );
    removeActiveSession(jobId);
    notification.success({
      message: 'Validation complete',
      description: result.summary.is_match ? 'All checks passed.' : 'View results in execution history.',
    });
    yield put(reportActions.fetchReportsRequest());
    yield* navigateToPairHistory(sourcePath, targetPath);
  } catch {
    removeActiveSession(jobId);
    yield put(reportActions.fetchReportsRequest());
  }
}

function* pollUntilCompleteOrDefer(
  jobId: string,
  sourcePath: string,
  targetPath: string,
) {
  const started = Date.now();
  let deferred = false;

  for (;;) {
    let job: import('axios').AxiosResponse<import('../../shared/api/Api').ValidationJobDetailResponse>;
    try {
      job = yield call(Api.getValidationJob, jobId, { summaryOnly: true });
    } catch (error: unknown) {
      if (!isTransientPollError(error)) throw error;
      yield delay(POLL_INTERVAL_MS);
      continue;
    }

    if (job.data.status === 'completed' && job.data.result) {
      return job.data.result;
    }
    if (job.data.status === 'failed') {
      throw new Error(job.data.error || 'Validation failed');
    }

    if (!deferred && Date.now() - started >= DEFER_TO_HISTORY_MS) {
      deferred = true;
      yield* navigateToPairHistory(sourcePath, targetPath);
      yield fork(backgroundPollSaga, jobId, sourcePath, targetPath);
      return null;
    }

    yield delay(POLL_INTERVAL_MS);
  }
}

function* submitValidationSaga() {
  let jobId: string | null = null;
  let sourcePath = '';
  let targetPath = '';
  try {
    const { validationForm, overviewProfileCache }: ValidationReducerState = yield select(
      (state: { validation: ValidationReducerState }) => state.validation,
    );
    if (!validationForm.sourceCloud || !validationForm.targetCloud) {
      throw new Error('Select source and target GCS objects before running validation');
    }

    sourcePath = gcsUri(validationForm.sourceCloud);
    targetPath = gcsUri(validationForm.targetCloud);

    const accepted: import('axios').AxiosResponse<ValidationJobAcceptedResponse> = yield call(
      Api.submitValidation,
      validateRequestFromForm(validationForm, undefined, {
        sourceProfile: overviewProfileCache?.source ?? null,
        targetProfile: overviewProfileCache?.target ?? null,
      }),
    );
    jobId = accepted.data.job_id;

    upsertActiveSession({
      jobId,
      sourcePath,
      targetPath,
      startedAt: Date.now(),
      formSnapshot: {
        sourceCloud: validationForm.sourceCloud,
        targetCloud: validationForm.targetCloud,
        uidColumn: validationForm.uidColumn,
        delimiter: validationForm.delimiter,
        hasHeader: validationForm.hasHeader,
        columnMappings: validationForm.columnMappings,
      },
    });
    yield put(reportActions.fetchReportsRequest());

    const result: import('../../shared/api/Api').ValidateResult | null = yield call(
      pollUntilCompleteOrDefer,
      jobId,
      sourcePath,
      targetPath,
    );
    if (result) {
      yield* submitValidationSuccess(jobId, result, sourcePath, targetPath);
    }
  } catch (error: unknown) {
    if (jobId) {
      try {
        const recovered: import('axios').AxiosResponse<import('../../shared/api/Api').ValidationJobDetailResponse> = yield call(
          Api.getValidationJob,
          jobId,
          { summaryOnly: true },
        );
        if (recovered.data.status === 'completed' && recovered.data.result) {
          yield* submitValidationSuccess(jobId, recovered.data.result, sourcePath, targetPath);
          return;
        }
      } catch {
        // fall through to user-visible error
      }
      const base = getApiErrorMessage(error, 'Validation failed');
      const hint = isTransientPollError(error) ? pollRecoveryHint(jobId) : '';
      removeActiveSession(jobId);
      yield put(validationActions.submitValidationError(base + hint));
      yield put(reportActions.fetchReportsRequest());
      return;
    }
    yield put(validationActions.submitValidationError(getApiErrorMessage(error, 'Validation submission failed')));
  }
}

function* runFromHistorySaga(action: ReturnType<typeof validationActions.runValidationFromHistoryRequest>) {
  const runId = action.payload;
  let jobId: string | null = null;
  let sourcePath = '';
  let targetPath = '';
  try {
    const { data: detail } = yield call(Api.getValidationHistoryRun, runId);
    const { data: connections } = yield call(ValidationServiceApi.listCloudConnections);
    const formPatch = enrichFormWithConnections(formFromHistory(detail), connections);
    yield put(validationActions.setValidationForm(formPatch));

    const { validationForm, overviewProfileCache }: ValidationReducerState = yield select(
      (state: { validation: ValidationReducerState }) => state.validation,
    );
    if (!validationForm.sourceCloud && !validationForm.targetCloud && !detail.source_path) {
      throw new Error('Saved mapping is missing cloud file paths');
    }

    sourcePath = validationForm.sourceCloud
      ? gcsUri(validationForm.sourceCloud)
      : (detail.source_path ?? '');
    targetPath = validationForm.targetCloud
      ? gcsUri(validationForm.targetCloud)
      : (detail.target_path ?? '');

    const accepted: import('axios').AxiosResponse<ValidationJobAcceptedResponse> = yield call(
      Api.submitValidation,
      validateRequestFromForm(validationForm, {
        source_path: detail.source_path,
        target_path: detail.target_path,
      }, {
        sourceProfile: overviewProfileCache?.source ?? null,
        targetProfile: overviewProfileCache?.target ?? null,
      }),
    );
    jobId = accepted.data.job_id;

    upsertActiveSession({
      jobId,
      sourcePath,
      targetPath,
      startedAt: Date.now(),
      formSnapshot: {
        sourceCloud: validationForm.sourceCloud,
        targetCloud: validationForm.targetCloud,
        uidColumn: validationForm.uidColumn,
        delimiter: validationForm.delimiter,
        hasHeader: validationForm.hasHeader,
        columnMappings: validationForm.columnMappings,
      },
    });
    yield put(reportActions.fetchReportsRequest());
    yield* navigateToPairHistory(sourcePath, targetPath);
    yield fork(backgroundPollSaga, jobId, sourcePath, targetPath);
  } catch (error: unknown) {
    if (jobId) removeActiveSession(jobId);
    notification.error({
      message: 'Could not start validation',
      description: getApiErrorMessage(error, 'Failed to run from saved configuration'),
    });
    yield put(validationActions.submitValidationError(getApiErrorMessage(error, 'Failed to run validation')));
  }
}

function* listCloudConnectionsSaga() {
  try {
    const response: import('axios').AxiosResponse<import('../../shared/api/Api').CloudConnection[]> = yield call(
      ValidationServiceApi.listCloudConnections,
    );
    yield put(validationActions.listCloudConnectionsSuccess(response.data));
  } catch (error: unknown) {
    yield put(validationActions.listCloudConnectionsError(
      getApiErrorMessage(error, 'Failed to load cloud connections'),
    ));
  }
}

function* browseCloudSaga(action: ReturnType<typeof validationActions.browseCloudRequest>) {
  const { pathId, connectionId, bucket, prefix } = action.payload;
  try {
    const response: import('axios').AxiosResponse<import('../../shared/api/Api').CloudBrowseResponse> = yield call(ValidationServiceApi.browseCloud, {
      connection_id: connectionId,
      bucket: bucket?.trim() ? bucket : null,
      prefix,
      file_format: 'auto',
    });
    yield put(validationActions.browseCloudSuccess({
      pathId,
      connectionId,
      data: response.data,
    }));
  } catch (error: unknown) {
    yield put(validationActions.browseCloudError({
      pathId,
      error: getApiErrorMessage(error, 'Could not browse GCS bucket. Check connection credentials.'),
    }));
  }
}

function* profileCloudFilesSaga(action: ReturnType<typeof validationActions.profileCloudFilesRequest>) {
  const { sourceKey, targetKey } = action.payload;
  const { validationForm }: ValidationReducerState = yield select(
    (state: { validation: ValidationReducerState }) => state.validation,
  );
  if (!validationForm.sourceCloud || !validationForm.targetCloud) return;

  let source: import('../../shared/api/Api').CloudFileProfileResponse | null = null;
  let target: import('../../shared/api/Api').CloudFileProfileResponse | null = null;
  let sourceError = false;
  let targetError = false;

  try {
    const sourceResponse: import('axios').AxiosResponse<import('../../shared/api/Api').CloudFileProfileResponse> = yield call(ValidationServiceApi.profileCloudFile, {
      cloud: validationForm.sourceCloud,
      delimiter: validationForm.delimiter || 'auto',
      has_header: validationForm.hasHeader,
    });
    source = sourceResponse.data;
  } catch {
    sourceError = true;
  }

  try {
    const targetResponse: import('axios').AxiosResponse<import('../../shared/api/Api').CloudFileProfileResponse> = yield call(ValidationServiceApi.profileCloudFile, {
      cloud: validationForm.targetCloud,
      delimiter: validationForm.delimiter || 'auto',
      has_header: validationForm.hasHeader,
    });
    target = targetResponse.data;
  } catch {
    targetError = true;
  }

  yield put(validationActions.setOverviewProfileCache({
    sourceKey,
    targetKey,
    source,
    target,
    sourceError,
    targetError,
  }));
}

function* previewValidationColumnsSaga(action: PayloadAction<string>) {
  const pairKey = action.payload;
  try {
    const { validationForm }: ValidationReducerState = yield select(
      (state: { validation: ValidationReducerState }) => state.validation,
    );
    if (!validationForm.sourceCloud || !validationForm.targetCloud) return;

    const response: import('axios').AxiosResponse<import('../../shared/api/Api').LocalColumnPreviewResponse> = yield call(ValidationServiceApi.previewValidationColumns, {
      source_cloud: validationForm.sourceCloud,
      target_cloud: validationForm.targetCloud,
      uid_column: validationForm.uidColumn || 'id',
      delimiter: validationForm.delimiter || 'auto',
      has_header: validationForm.hasHeader,
    });
    yield put(validationActions.previewValidationColumnsSuccess({ pairKey, data: response.data }));
  } catch (error: unknown) {
    yield put(validationActions.previewValidationColumnsError({
      pairKey,
      error: getApiErrorMessage(error, 'Could not load file preview from server'),
    }));
  }
}

function* previewFixedWidthLayoutSaga(action: PayloadAction<string>) {
  const pairKey = action.payload;
  try {
    const { validationForm }: ValidationReducerState = yield select(
      (state: { validation: ValidationReducerState }) => state.validation,
    );
    if (!validationForm.sourceCloud || !validationForm.targetCloud) return;

    const response: import('axios').AxiosResponse<import('../../shared/api/Api').FixedWidthLayoutPreviewResponse> = yield call(ValidationServiceApi.previewFixedWidthLayout, {
      source_cloud: validationForm.sourceCloud,
      target_cloud: validationForm.targetCloud,
      uid_column: validationForm.uidColumn,
      delimiter: validationForm.delimiter || 'auto',
      has_header: validationForm.hasHeader,
    });
    yield put(validationActions.previewFixedWidthLayoutSuccess({ pairKey, data: response.data }));
  } catch (error: unknown) {
    yield put(validationActions.previewFixedWidthLayoutError({
      pairKey,
      error: getApiErrorMessage(error, 'Could not infer fixed-width layout'),
    }));
  }
}

function* saveDraftSaga(action: ReturnType<typeof validationActions.saveDraftRequest>) {
  try {
    const response: import('axios').AxiosResponse<import('../../shared/api/Api').ValidationHistoryDetail> = yield call(ValidationServiceApi.saveValidationDraft, action.payload.draft);
    yield put(validationActions.saveDraftSuccess(response.data));
    if (action.payload.intent === 'save') {
      notification.success({
        message: NOTIFICATION_SERVICE_TYPES.SUCCESS,
        description: 'Find it under Reports → Saved.',
      });
      yield put(reportActions.fetchReportsRequest());
    }
  } catch (error: unknown) {
    const fallback = action.payload.intent === 'proceed'
      ? 'Failed to create validation run'
      : 'Save failed';
    const errorMessage = getApiErrorMessage(error, fallback);
    yield put(validationActions.saveDraftError(errorMessage));
    if (error instanceof AxiosError) {
      notification.error({
        message: action.payload.intent === 'proceed'
          ? 'Could not start file overview'
          : NOTIFICATION_SERVICE_TYPES.ERROR,
        description: errorMessage,
      });
    }
  }
}

export default function* validationSaga() {
  yield all([
    takeLatest(validationActions.submitValidationRequest.type, submitValidationSaga),
    takeLatest(validationActions.runValidationFromHistoryRequest.type, runFromHistorySaga),
    takeLatest(validationActions.listCloudConnectionsRequest.type, listCloudConnectionsSaga),
    takeLatest(validationActions.browseCloudRequest.type, browseCloudSaga),
    takeLatest(validationActions.profileCloudFilesRequest.type, profileCloudFilesSaga),
    takeLatest(validationActions.previewValidationColumnsRequest.type, previewValidationColumnsSaga),
    takeLatest(validationActions.previewFixedWidthLayoutRequest.type, previewFixedWidthLayoutSaga),
    takeLatest(validationActions.saveDraftRequest.type, saveDraftSaga),
  ]);
}
