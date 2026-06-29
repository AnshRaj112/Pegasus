import { call, delay, put, select, takeLatest } from 'redux-saga/effects';
import { PayloadAction } from '@reduxjs/toolkit';
import { notification } from 'antd';

import { getApiErrorMessage } from '../../shared/api/apiError';
import { NOTIFICATION_SERVICE_TYPES } from '~/shared/constants/common.constants';
import {
 AdminReducerState,
 CreateStorageProviderPayload,
 StorageProviderItem,
 StorageProviderPayload,
 WorkspaceItem,
} from './Admin.interface';
import { adminActions } from './Admin.reducer';
import { adminService } from './Admin.service';

export function* handleTestConnectionSaga(action: PayloadAction<string>) {
  const connectionId = action.payload;
  try {
    const adminState: AdminReducerState = yield select((state: { admin: AdminReducerState }) => state.admin);
    const provider = adminState.storageProviders.data.find((p) => p.id === connectionId);
    const response: { status: 'success' | 'failed' } = yield call(
      [adminService, adminService.testConnection],
      connectionId,
      provider?.bucket,
    );

    if (response.status === 'success') {
      yield put(adminActions.testConnectionSuccess(connectionId));
      yield delay(2500);
      yield put(adminActions.resetConnectionTest(connectionId));
    }
  } catch (error: unknown) {
    yield put(adminActions.testConnectionFailure(connectionId));
    notification.error({
      message: NOTIFICATION_SERVICE_TYPES.ERROR,
      description: getApiErrorMessage(error, 'Could not reach the storage bucket.'),
    });
    yield delay(2500);
    yield put(adminActions.resetConnectionTest(connectionId));
  }
}

export function* handleFetchWorkspacesSaga() {
  try {
    const data: WorkspaceItem[] = yield call([adminService, adminService.fetchWorkspaces]);
    yield put(adminActions.fetchWorkspacesSuccess(data));
  } catch (error: unknown) {
    yield put(adminActions.fetchWorkspacesError(getApiErrorMessage(error, 'Failed to fetch workspaces')));
  }
}

export function* handleFetchProvidersSaga() {
  try {
    const data: StorageProviderItem[] = yield call([adminService, adminService.fetchStorageProviders]);
    yield put(adminActions.fetchProvidersSuccess(data));
  } catch (error: unknown) {
    yield put(adminActions.fetchProvidersError(getApiErrorMessage(error, 'Failed to fetch storage connections')));
  }
}

export function* handleCreateProviderSaga(action: PayloadAction<CreateStorageProviderPayload>) {
  try {
    const created: StorageProviderItem = yield call(
      [adminService, adminService.createStorageProvider],
      action.payload,
    );
    yield put(adminActions.createProviderSuccess(created));
    notification.success({
      message: NOTIFICATION_SERVICE_TYPES.SUCCESS,
      description: `${created.name} is ready to use in validation workflows.`,
    });
  } catch (error: unknown) {
    yield put(adminActions.createProviderError(getApiErrorMessage(error, 'Failed to create storage connection')));
  }
}

export function* handleUpdateProviderSaga(action: PayloadAction<StorageProviderPayload>) {
  try {
    const updated: StorageProviderItem = yield call(
      [adminService, adminService.updateStorageProvider],
      action.payload,
    );
    yield put(adminActions.updateProviderSuccess(updated));
    notification.success({
      message: NOTIFICATION_SERVICE_TYPES.SUCCESS,
      description: `${updated.name} has been saved.`,
    });
  } catch (error: unknown) {
    yield put(adminActions.updateProviderError(getApiErrorMessage(error, 'Failed to update storage connection')));
  }
}

export function* handleDeleteProviderSaga(action: PayloadAction<string>) {
  try {
    yield call([adminService, adminService.deleteStorageProvider], action.payload);
    yield put(adminActions.deleteProviderSuccess(action.payload));
    notification.success({
      message: NOTIFICATION_SERVICE_TYPES.SUCCESS,
      description: 'Storage connection removed',
    });
  } catch (error: unknown) {
    yield put(adminActions.deleteProviderError(getApiErrorMessage(error, 'Failed to delete storage connection')));
  }
}

export default function* adminSaga() {
  yield takeLatest(adminActions.testConnectionRequest.type, handleTestConnectionSaga);
  yield takeLatest(adminActions.fetchWorkspacesRequest.type, handleFetchWorkspacesSaga);
  yield takeLatest(adminActions.fetchProvidersRequest.type, handleFetchProvidersSaga);
  yield takeLatest(adminActions.createProviderRequest.type, handleCreateProviderSaga);
  yield takeLatest(adminActions.updateProviderRequest.type, handleUpdateProviderSaga);
  yield takeLatest(adminActions.deleteProviderRequest.type, handleDeleteProviderSaga);
}
