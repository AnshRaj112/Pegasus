import { notification } from 'antd';
import { AxiosError } from 'axios';
import { all, call, put, select, takeLatest } from 'redux-saga/effects';

import { getApiErrorMessage } from '../../shared/api/apiError';
import { NOTIFICATION_SERVICE_TYPES } from '../../shared/constants/common.constant';
import { type RootState } from '../../redux/store';

import { historyActions } from './History.reducer';
import { historyService } from './History.service';
import { type MappingLogItem, type ValidationLogItem } from './History.interface';

function* fetchValidationLogsSaga() {
  const { page, pageSize }: { page: number; pageSize: number } = yield select((state: RootState) => ({
    page: state.history.validationLogs.page,
    pageSize: state.history.pageSize,
  }));
  const offset = (page - 1) * pageSize;
  const result: { items: ValidationLogItem[]; total: number } = yield call(
    historyService.fetchValidationLogs,
    pageSize,
    offset,
  );
  yield put(historyActions.fetchValidationLogsSuccess(result));
}

function* fetchMappingLogsSaga() {
  const { page, pageSize }: { page: number; pageSize: number } = yield select((state: RootState) => ({
    page: state.history.mappingLogs.page,
    pageSize: state.history.pageSize,
  }));
  const offset = (page - 1) * pageSize;
  const result: { items: MappingLogItem[]; total: number } = yield call(
    historyService.fetchMappingLogs,
    pageSize,
    offset,
  );
  yield put(historyActions.fetchMappingLogsSuccess(result));
}

function* handleFetchHistorySaga(action: ReturnType<typeof historyActions.fetchHistoryRequest>) {
  const tab: 'validation' | 'mapping' =
    action.payload?.tab ?? (yield select((state: RootState) => state.history.activeTab));
  try {
    if (tab === 'validation') {
      yield call(fetchValidationLogsSaga);
    } else {
      yield call(fetchMappingLogsSaga);
    }
  } catch (error) {
    const errorMessage = getApiErrorMessage(error, 'Failed to fetch history data');
    yield put(historyActions.fetchHistoryFailure({ tab, error: errorMessage }));
    if (error instanceof AxiosError) {
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: errorMessage,
      });
    }
  }
}

function* handleDeleteValidationLogSaga(action: ReturnType<typeof historyActions.deleteValidationLog>) {
  try {
    yield call(historyService.deleteLogRecord, action.payload);
  } catch (error) {
    const errorMessage = getApiErrorMessage(error, 'Failed to delete record');
    notification.error({
      message: NOTIFICATION_SERVICE_TYPES.ERROR,
      description: errorMessage,
    });
    yield put(historyActions.fetchHistoryRequest({ tab: 'validation' }));
  }
}

function* handleDeleteMappingLogSaga(action: ReturnType<typeof historyActions.deleteMappingLog>) {
  try {
    yield call(historyService.deleteLogRecord, action.payload);
  } catch (error) {
    const errorMessage = getApiErrorMessage(error, 'Failed to delete record');
    notification.error({
      message: NOTIFICATION_SERVICE_TYPES.ERROR,
      description: errorMessage,
    });
    yield put(historyActions.fetchHistoryRequest({ tab: 'mapping' }));
  }
}

function* handleSetPageSaga(action: ReturnType<typeof historyActions.setPage>) {
  yield call(handleFetchHistorySaga, historyActions.fetchHistoryRequest({ tab: action.payload.tab }));
}

export default function* historySaga() {
  yield all([
    takeLatest(historyActions.fetchHistoryRequest.type, handleFetchHistorySaga),
    takeLatest(historyActions.deleteValidationLog.type, handleDeleteValidationLogSaga),
    takeLatest(historyActions.deleteMappingLog.type, handleDeleteMappingLogSaga),
    takeLatest(historyActions.setPage.type, handleSetPageSaga),
  ]);
}
