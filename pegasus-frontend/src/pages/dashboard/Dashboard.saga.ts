import { notification } from 'antd';
import { AxiosError, type AxiosResponse } from 'axios';
import { all, call, put, takeLatest } from 'redux-saga/effects';

import { getApiErrorMessage } from '../../shared/api/apiError';
import { NOTIFICATION_SERVICE_TYPES } from '../../shared/constants/common.constant';

import { type DashboardDataResponse } from './Dashboard.interface';
import { dashboardActions } from './Dashboard.reducer';
import { DashboardServiceApi } from './Dashboard.service';

export function* fetchDashboardDataSaga() {
  try {
    const response: AxiosResponse<DashboardDataResponse> = yield call(DashboardServiceApi.fetchDashboardData);
    yield put(dashboardActions.fetchDashboardDataSuccess(response.data));
  } catch (error) {
    const errorMessage = getApiErrorMessage(error, 'Failed to fetch dashboard data');
    yield put(dashboardActions.fetchDashboardDataError(errorMessage));
    if (error instanceof AxiosError) {
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: errorMessage,
      });
    }
  }
}

export function* dashboardSaga() {
  yield all([
    takeLatest(dashboardActions.fetchDashboardDataRequest.type, fetchDashboardDataSaga),
  ]);
}