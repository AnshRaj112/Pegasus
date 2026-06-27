import { all } from 'redux-saga/effects';

import { dashboardSaga } from '../pages/dashboard/Dashboard.saga';
import validationSaga from '../pages/validation/Validation.saga';
import adminSaga from '../pages/admin/Admin.saga';
import { reportSaga } from '../pages/report/Report.saga';
import { profileSaga } from '../pages/profile/Profile.saga';
import {settingSaga} from '../pages/admin/sections/setting/Setting.saga';
import { testSaga } from '~/pages/test/Test.saga';


export default function* rootSaga() {
  yield all([
    dashboardSaga(),
    validationSaga(),
    adminSaga(),
    reportSaga(),
    profileSaga(),
    settingSaga(),
    testSaga(),
  ]);
}