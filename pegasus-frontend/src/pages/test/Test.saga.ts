import { notification } from 'antd';
import { AxiosError } from 'axios';
import { all, put, takeLatest, delay } from 'redux-saga/effects';
import { NOTIFICATION_SERVICE_TYPES } from '~/shared/constants/common.constant';
import { testActions } from './Test.reducer';
import { mockActiveTests, mockCompletedTests, mockSavedTests } from './Test.mockdata';

export function* fetchActiveTestsSaga() {
  try {
    // Simulate network latency to test skeleton loaders
    yield delay(800); 
    
    // Bypass TestServiceApi for now and yield the mock data directly
    yield put(testActions.fetchActiveTestsSuccess(mockActiveTests));
  } catch (error) {
    if (error instanceof AxiosError) {
      yield put(testActions.fetchActiveTestsError(error.response?.data?.message || 'Error'));
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: error.response?.data?.message || 'Failed to load active tests.',
      });
    }
  }
}

export function* fetchCompletedTestsSaga() {
  try {
    yield delay(800); 
    yield put(testActions.fetchCompletedTestsSuccess(mockCompletedTests));
  } catch (error) {
    if (error instanceof AxiosError) {
      yield put(testActions.fetchCompletedTestsError(error.response?.data?.message || 'Error'));
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: error.response?.data?.message || 'Failed to load completed tests.',
      });
    }
  }
}

export function* fetchSavedTestsSaga() {
  try {
    yield delay(800);
    yield put(testActions.fetchSavedTestsSuccess(mockSavedTests));
  } catch (error) {
    if (error instanceof AxiosError) {
      yield put(testActions.fetchSavedTestsError(error.response?.data?.message || 'Error'));
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