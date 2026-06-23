import { all } from 'redux-saga/effects';

import { dashboardSaga } from '../pages/dashboard/Dashboard.saga';
import validationSaga from '../pages/validation/Validation.saga';
import adminSaga from '../pages/admin/Admin.saga';
import { reportSaga } from '../pages/report/Report.saga';

export default function* rootSaga() {
  yield all([
    dashboardSaga(),
    validationSaga(),
    adminSaga(),
    reportSaga(),
  ]);
}