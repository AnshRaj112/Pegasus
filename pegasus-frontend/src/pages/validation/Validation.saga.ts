import { type AxiosResponse } from 'axios';
import { call, put, select, takeLatest } from 'redux-saga/effects';

import { Api, type ValidationJobAcceptedResponse } from '../../shared/api/Api';
import { getApiErrorMessage, isTransientPollError, pollRecoveryHint } from '../../shared/api/apiError';

import { type ValidationDataResponse, type ValidationReducerState } from './Validation.interface';
import { validationActions } from './Validation.reducer';

function* submitValidationSuccess(
  jobId: string,
  result: import('../../shared/api/Api').ValidateResult,
) {
  const payload: ValidationDataResponse = {
    jobId,
    runId: result.run_id ?? null,
    status: 'Complete',
    results: result,
  };
  yield put(validationActions.submitValidationSuccess(payload));
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
      column_mappings: validationForm.columnMappings,
    });
    jobId = accepted.data.job_id;

    const result: import('../../shared/api/Api').ValidateResult = yield call(
      Api.pollValidationUntilComplete,
      jobId,
    );
    yield* submitValidationSuccess(jobId, result);
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
      yield put(validationActions.submitValidationError(base + hint));
      return;
    }
    yield put(validationActions.submitValidationError(getApiErrorMessage(error, 'Validation submission failed')));
  }
}

export default function* validationSaga() {
  yield takeLatest(validationActions.submitValidationRequest.type, submitValidationSaga);
}
