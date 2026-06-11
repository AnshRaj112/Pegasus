import { type AxiosResponse } from 'axios';
import { call, put, takeLatest } from 'redux-saga/effects';

import { type ValidationDataResponse } from './Validation.interface';
import { validationActions } from './Validation.reducer';
import { ValidationServiceApi } from './Validation.service';

function* submitValidationSaga() {
  try {
    const response: AxiosResponse<ValidationDataResponse> = yield call(ValidationServiceApi.submitValidation);
    yield put(validationActions.submitValidationSuccess(response.data));
  } catch (error: any) {
    yield put(validationActions.submitValidationError(error.message || 'Validation submission failed'));
  }
}

export default function* validationSaga() {
  yield takeLatest(validationActions.submitValidationRequest.type, submitValidationSaga);
}