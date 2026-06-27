import { notification } from 'antd';
import { AxiosError } from 'axios';
import { all, call, put, takeLatest } from 'redux-saga/effects';

import { getApiErrorMessage } from '../../shared/api/apiError';
import { NOTIFICATION_SERVICE_TYPES } from '../../shared/constants/common.constant';

import { profileActions } from './Profile.reducer';
import { fetchUserProfile } from './Profile.service';

export function* fetchProfileSaga() {
  try {
    const data: Awaited<ReturnType<typeof fetchUserProfile>> = yield call(fetchUserProfile);
    yield put(profileActions.fetchProfileSuccess(data));
  } catch (error) {
    const errorMessage = getApiErrorMessage(error, 'Failed to fetch profile');
    yield put(profileActions.fetchProfileError(errorMessage));
    if (error instanceof AxiosError) {
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: errorMessage,
      });
    }
  }
}

export function* profileSaga() {
  yield all([
    takeLatest(profileActions.fetchProfileRequest.type, fetchProfileSaga),
  ]);
}
