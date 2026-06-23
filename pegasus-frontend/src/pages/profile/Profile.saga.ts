import { call, put, takeLatest } from 'redux-saga/effects';
import { fetchUserProfile } from './Profile.service';

function* handleFetchProfile(): Generator<any, void, any> {
  try {
    const data = yield call(fetchUserProfile);
    yield put({ type: 'FETCH_PROFILE_SUCCESS', payload: data });
  } catch (error: any) {
    yield put({ type: 'FETCH_PROFILE_FAILURE', payload: error.message });
  }
}

export function* watchProfileSagas() {
  yield takeLatest('FETCH_PROFILE_REQUEST', handleFetchProfile);
}