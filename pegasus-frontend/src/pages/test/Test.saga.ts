import { notification } from 'antd';
import { AxiosError, AxiosResponse } from 'axios';
import { all, call, put, takeLatest } from 'redux-saga/effects';
import { NOTIFICATION_SERVICE_TYPES } from '~/shared/constants/common.constant';
import { testActions } from './Test.reducer';
import { TestEntity } from './Test.interface';
import { TestServiceApi } from './Test.service';

export function* fetchActiveTestsSaga() {
  try {
    const response: AxiosResponse<TestEntity[]> = yield call(TestServiceApi.fetchActiveTests);
    yield put(testActions.fetchActiveTestsSuccess(response.data));
  } catch (error) {
    if (error instanceof AxiosError) {
      yield put(testActions.fetchActiveTestsError(error.response?.data?.message || 'Error fetching active tests'));
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: error.response?.data?.message || 'Failed to load active tests.',
      });
    }
  }
}

export function* fetchCompletedTestsSaga() {
  try {
    const response: AxiosResponse<TestEntity[]> = yield call(TestServiceApi.fetchCompletedTests);
    yield put(testActions.fetchCompletedTestsSuccess(response.data));
  } catch (error) {
    if (error instanceof AxiosError) {
      yield put(testActions.fetchCompletedTestsError(error.response?.data?.message || 'Error fetching completed tests'));
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: error.response?.data?.message || 'Failed to load completed tests.',
      });
    }
  }
}

export function* fetchSavedTestsSaga() {
  try {
    const response: AxiosResponse<TestEntity[]> = yield call(TestServiceApi.fetchSavedTests);
    yield put(testActions.fetchSavedTestsSuccess(response.data));
  } catch (error) {
    if (error instanceof AxiosError) {
      yield put(testActions.fetchSavedTestsError(error.response?.data?.message || 'Error fetching saved tests'));
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: error.response?.data?.message || 'Failed to load saved tests.',
      });
    }
  }
}

export function* testSaga() {
  yield all([
    takeLatest(testActions.fetchActiveTestsRequest.type, fetchActiveTestsSaga),
    takeLatest(testActions.fetchCompletedTestsRequest.type, fetchCompletedTestsSaga),
    takeLatest(testActions.fetchSavedTestsRequest.type, fetchSavedTestsSaga),
  ]);
}