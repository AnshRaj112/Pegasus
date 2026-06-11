import { type AxiosResponse } from 'axios';
import { call, put, select, takeLatest } from 'redux-saga/effects';

import { Api, type ValidationJobAcceptedResponse } from '../../shared/api/Api';
import { getApiErrorMessage } from '../../shared/api/apiError';

import { type ValidationDataResponse, type ValidationReducerState } from './Validation.interface';
import { validationActions } from './Validation.reducer';

function* submitValidationSaga() {
  try {
    const { validationForm }: ValidationReducerState = yield select(
      (state: { validation: ValidationReducerState }) => state.validation,
    );
    if (!validationForm.sourcePath || !validationForm.targetPath) {
      throw new Error('Select source and target files before running validation');
    }

    const accepted: AxiosResponse<ValidationJobAcceptedResponse> = yield call(Api.submitValidation, {
      source_path: validationForm.sourcePath,
      target_path: validationForm.targetPath,
      uid_column: validationForm.uidColumn,
      delimiter: validationForm.delimiter || 'auto',
      column_mappings: validationForm.columnMappings,
    });

    const result: import('../../shared/api/Api').ValidateResult = yield call(
      Api.pollValidationUntilComplete,
      accepted.data.job_id,
    );
    const payload: ValidationDataResponse = {
      jobId: accepted.data.job_id,
      runId: result.run_id ?? null,
      status: 'Complete',
      results: result,
    };
    yield put(validationActions.submitValidationSuccess(payload));
  } catch (error: unknown) {
    yield put(validationActions.submitValidationError(getApiErrorMessage(error, 'Validation submission failed')));
  }
}

export default function* validationSaga() {
  yield takeLatest(validationActions.submitValidationRequest.type, submitValidationSaga);
}
