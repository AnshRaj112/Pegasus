import { call, put, takeLatest } from 'redux-saga/effects';
import { historyActions } from './History.reducer';
import { historyService } from './History.service';

function* handleFetchHistorySaga() {
  try {
    // Future implementation: Fetch data from service and dispatch success actions
    yield call(historyService.fetchValidationLogs);
    yield call(historyService.fetchMappingLogs);
  } catch (error) {
    console.error('Failed to fetch history data', error);
  }
}

export default function* historySaga() {
  yield takeLatest(historyActions.fetchHistoryRequest.type, handleFetchHistorySaga);
}