import {  delay, put, takeLatest } from 'redux-saga/effects';
import { type PayloadAction } from '@reduxjs/toolkit';
import { adminActions } from './Admin.reducer';
// import { adminService } from './Admin.service';
// import { type WorkspaceItem, type StorageProviderItem } from './Admin.interface';

// --- 1. Worker Saga: Test Connection ---
function* handleTestConnectionSaga(action: PayloadAction<string>) {
  try {
    // ⚡ Artificial delay just for UX (so users see the smooth loading spinner)
    yield delay(800); 
    
    // ⚡ Make the actual API call through our Service Layer
    // const response: { status: 'success' | 'failed' } = yield call(adminService.testConnection, action.payload);
    
    // ⚡ If the API returns success, tell the Reducer to update the UI
    // if (response.status === 'success') {
    //   yield put(adminActions.testConnectionSuccess(action.payload));
    // }
    
    // Clear the success message after 2 seconds to reset the UI
    yield delay(2000);
    yield put(adminActions.resetConnectionTest(action.payload));
    
  } catch (error: any) {
    console.error('Connection test failed', error);
    // In the future, you can dispatch an error action to the reducer here
  }
}

// --- 2. Worker Saga: Fetch Workspaces (Future-Proofing) ---
function* handleFetchWorkspacesSaga() {
  try {
    // ⚡ Calls the service to get the data array
    // const data: WorkspaceItem[] = yield call(adminService.fetchWorkspaces);
    
    // Note: Commented out for now so it doesn't overwrite your beautiful Redux mock data with an empty array!
    // yield put(adminActions.fetchWorkspacesSuccess(data)); 
  } catch (error: any) {
    yield put(adminActions.fetchWorkspacesError(error.message || 'Failed to fetch workspaces'));
  }
}

// --- 3. Worker Saga: Fetch Storage Providers (Future-Proofing) ---
function* handleFetchProvidersSaga() {
  try {
    // ⚡ Calls the service to get the data array
    // const data: StorageProviderItem[] = yield call(adminService.fetchStorageProviders);
    
    // Note: Commented out for now
    // yield put(adminActions.fetchProvidersSuccess(data));
  } catch (error: any) {
    console.error('Failed to fetch providers', error);
  }
}

// --- Watcher Saga ---
export default function* adminSaga() {
  // This listens for actions dispatched from the UI and triggers the correct Worker Saga above
  yield takeLatest(adminActions.testConnectionRequest.type, handleTestConnectionSaga);
  yield takeLatest(adminActions.fetchWorkspacesRequest.type, handleFetchWorkspacesSaga);
  yield takeLatest(adminActions.fetchProvidersRequest.type, handleFetchProvidersSaga);
}