import { notification } from 'antd';
import { AxiosError } from 'axios';
import { PayloadAction } from '@reduxjs/toolkit';
import { all, call, put, select, takeLatest } from 'redux-saga/effects';

import { getApiErrorMessage } from '../../shared/api/apiError';
import { NOTIFICATION_SERVICE_TYPES } from '~/shared/constants/common.constants';

import { ReportItem, ReportState, TabType } from './Report.interface';
import { reportActions } from './Report.reducer';
import { ReportService } from './Report.service';

/** Snippet view only needs the persisted sample; one request is enough (API max page size). */
const SNIPPET_FETCH_LIMIT = 5000;

const selectActiveTab = (state: { report: { activeTab: TabType } }): TabType => state.report.activeTab;
const selectHistoryRunState = (state: { report: ReportState }) => state.report.historyRunState;
const selectMismatchesState = (state: { report: ReportState }) => state.report.mismatchesState;

export function* handleFetchActiveReports() {
  try {
    const data: ReportItem[] = yield call(ReportService.fetchActive);
    yield put(reportActions.fetchReportsSuccess({ tab: 'Active', data }));
  } catch (error) {
    const errorMessage = getApiErrorMessage(error, 'Failed to fetch active reports');
    yield put(reportActions.fetchReportsFailure({ tab: 'Active', error: errorMessage }));
    if (error instanceof AxiosError) {
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: errorMessage,
      });
    }
  }
}

export function* handleFetchReports() {
  const activeTab: TabType = yield select(selectActiveTab);

  try {
    let data: ReportItem[] = [];

    if (activeTab === 'Active') {
      data = yield call(ReportService.fetchActive);
    } else if (activeTab === 'Completed') {
      data = yield call(ReportService.fetchCompleted);
    } else if (activeTab === 'Saved') {
      data = yield call(ReportService.fetchSaved);
    }

    yield put(reportActions.fetchReportsSuccess({ tab: activeTab, data }));
  } catch (error) {
    const errorMessage = getApiErrorMessage(error, 'Failed to fetch reports');
    yield put(reportActions.fetchReportsFailure({ tab: activeTab, error: errorMessage }));
    if (error instanceof AxiosError) {
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: errorMessage,
      });
    }
  }
}

export function* fetchHistoryRunSaga(action: PayloadAction<string>) {
  const runId = action.payload;
  const existing: ReportState['historyRunState'] = yield select(selectHistoryRunState);
  if (existing.runId === runId && existing.data) {
    return;
  }
  try {
    const data: import('../../shared/api/Api').ValidationHistoryDetail = yield call(ReportService.fetchHistoryRun, runId);
    yield put(reportActions.fetchHistoryRunSuccess({ runId, data }));
  } catch (error) {
    const errorMessage = getApiErrorMessage(error, 'Failed to load validation run');
    yield put(reportActions.fetchHistoryRunError({ runId, error: errorMessage }));
    if (error instanceof AxiosError) {
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: errorMessage,
      });
    }
  }
}

export function* fetchMismatchesSaga(action: PayloadAction<string>) {
  const runId = action.payload;
  const existing: ReportState['mismatchesState'] = yield select(selectMismatchesState);
  if (existing.runId === runId && existing.isComplete) {
    return;
  }

  try {
    const page: import('../../shared/api/Api').ValidationMismatchesResponse = yield call(
      ReportService.fetchMismatchesPage,
      runId,
      { limit: SNIPPET_FETCH_LIMIT, offset: 0 },
    );

    yield put(reportActions.fetchMismatchesSuccess({
      runId,
      items: page.items,
      total: page.total,
    }));
  } catch (error) {
    const errorMessage = getApiErrorMessage(error, 'Failed to load mismatch rows');
    yield put(reportActions.fetchMismatchesError({ runId, error: errorMessage }));
    if (error instanceof AxiosError) {
      notification.error({
        message: NOTIFICATION_SERVICE_TYPES.ERROR,
        description: errorMessage,
      });
    }
  }
}

export function* reportSaga() {
  yield all([
    takeLatest(reportActions.fetchReportsRequest.type, handleFetchReports),
    takeLatest(reportActions.fetchActiveReportsRequest.type, handleFetchActiveReports),
    takeLatest(reportActions.setTab.type, handleFetchReports),
    takeLatest(reportActions.fetchHistoryRunRequest.type, fetchHistoryRunSaga),
    takeLatest(reportActions.fetchMismatchesRequest.type, fetchMismatchesSaga),
  ]);
}
