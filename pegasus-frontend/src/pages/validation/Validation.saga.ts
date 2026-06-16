import { type AxiosResponse } from 'axios';
import { call, delay, fork, put, select, takeLatest } from 'redux-saga/effects';
import { notification } from 'antd';

import { Api, type ValidationJobAcceptedResponse } from '../../shared/api/Api';
import { getApiErrorMessage, isTransientPollError, pollRecoveryHint } from '../../shared/api/apiError';
import { reportActions } from '../report/Report.reducer';
import { gcsUri } from '../report/reportPairId';

import { type ValidationDataResponse, type ValidationReducerState } from './Validation.interface';
import { validationActions } from './Validation.reducer';
import {
  removeActiveSession,
  upsertActiveSession,
} from './validationSessionStorage';
import { formFromHistory, enrichFormWithConnections, validateRequestFromForm } from './validationRerun';

const DEFER_TO_REPORT_MS = 10_000;
const POLL_INTERVAL_MS = 2_000;

function* submitValidationSuccess(
  jobId: string,
  result: import('../../shared/api/Api').ValidateResult,
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
}

function* backgroundPollSaga(jobId: string) {
  try {
    const result: import('../../shared/api/Api').ValidateResult = yield call(
      Api.pollValidationUntilComplete,
      jobId,
    );
    removeActiveSession(jobId);
    notification.success({
      message: 'Validation complete',
      description: result.summary.is_match ? 'All checks passed.' : 'Report is ready to review.',
    });
    yield put(reportActions.fetchReportsRequest());
  } catch {
    removeActiveSession(jobId);
    yield put(reportActions.fetchReportsRequest());
  }
}

function* pollUntilCompleteOrDefer(jobId: string) {
  const started = Date.now();
  let deferred = false;

  for (;;) {
    let job: AxiosResponse<import('../../shared/api/Api').ValidationJobDetailResponse>;
    try {
      job = yield call(Api.getValidationJob, jobId);
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

    if (!deferred && Date.now() - started >= DEFER_TO_REPORT_MS) {
      deferred = true;
      yield put(validationActions.validationDeferredToReport({ jobId }));
      yield fork(backgroundPollSaga, jobId);
      return null;
    }

    yield delay(POLL_INTERVAL_MS);
  }
}

function* submitValidationSaga() {
  let jobId: string | null = null;
  try {
    const { validationForm }: ValidationReducerState = yield select(
      (state: { validation: ValidationReducerState }) => state.validation,
    );
    if (!validationForm.sourceCloud || !validationForm.targetCloud) {
      throw new Error('Select source and target GCS objects before running validation');
    }

    const accepted: AxiosResponse<ValidationJobAcceptedResponse> = yield call(Api.submitValidation, {
      source_cloud: validationForm.sourceCloud,
      target_cloud: validationForm.targetCloud,
      uid_column: validationForm.uidColumn,
      delimiter: validationForm.delimiter || 'auto',
      has_header: validationForm.hasHeader,
      column_mappings: validationForm.columnMappings,
    });
    jobId = accepted.data.job_id;

    upsertActiveSession({
      jobId,
      sourcePath: gcsUri(validationForm.sourceCloud),
      targetPath: gcsUri(validationForm.targetCloud),
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
    );
    if (result) {
      yield* submitValidationSuccess(jobId, result);
    }
  } catch (error: unknown) {
    if (jobId) {
      try {
        const recovered: AxiosResponse<import('../../shared/api/Api').ValidationJobDetailResponse> = yield call(
          Api.getValidationJob,
          jobId,
        );
        if (recovered.data.status === 'completed' && recovered.data.result) {
          yield* submitValidationSuccess(jobId, recovered.data.result);
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
  try {
    const { data: detail } = yield call(Api.getValidationHistoryRun, runId);
    const { data: connections } = yield call(Api.listCloudConnections);
    const formPatch = enrichFormWithConnections(formFromHistory(detail), connections);
    yield put(validationActions.setValidationForm(formPatch));

    const { validationForm }: ValidationReducerState = yield select(
      (state: { validation: ValidationReducerState }) => state.validation,
    );
    if (!validationForm.sourceCloud && !validationForm.targetCloud && !detail.source_path) {
      throw new Error('Saved mapping is missing cloud file paths');
    }

    const accepted: AxiosResponse<ValidationJobAcceptedResponse> = yield call(
      Api.submitValidation,
      validateRequestFromForm(validationForm, {
        source_path: detail.source_path,
        target_path: detail.target_path,
      }),
    );
    jobId = accepted.data.job_id;

    const src = validationForm.sourceCloud ? gcsUri(validationForm.sourceCloud) : (detail.source_path ?? '');
    const tgt = validationForm.targetCloud ? gcsUri(validationForm.targetCloud) : (detail.target_path ?? '');
    upsertActiveSession({
      jobId,
      sourcePath: src,
      targetPath: tgt,
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
    yield put(validationActions.validationDeferredToReport({ jobId }));
    yield fork(backgroundPollSaga, jobId);
  } catch (error: unknown) {
    if (jobId) removeActiveSession(jobId);
    notification.error({
      message: 'Could not start validation',
      description: getApiErrorMessage(error, 'Failed to run from saved configuration'),
    });
    yield put(validationActions.submitValidationError(getApiErrorMessage(error, 'Failed to run validation')));
  }
}

export default function* validationSaga() {
  yield takeLatest(validationActions.submitValidationRequest.type, submitValidationSaga);
  yield takeLatest(validationActions.runValidationFromHistoryRequest.type, runFromHistorySaga);
}
