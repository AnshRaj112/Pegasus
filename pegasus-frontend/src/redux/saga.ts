import { all } from 'redux-saga/effects';

import { dashboardSaga } from '../pages/dashboard/Dashboard.saga';
import validationSaga from '../pages/validation/Validation.saga';

export default function* rootSaga() {
  yield all([
    dashboardSaga(),
    validationSaga(),
  ]);
}