import { notification } from 'antd';
import { AxiosError } from 'axios';
import { PayloadAction } from '@reduxjs/toolkit';
import { all, call, delay, put, select, takeLatest } from 'redux-saga/effects';

import { MismatchSampleRow } from '../../shared/api/Api';
import { getApiErrorMessage } from '../../shared/api/apiError';
import { NOTIFICATION_SERVICE_TYPES } from '../../shared/constants/common.constant';

import { ReportItem, TabType } from './Report.interface';
import { reportActions } from './Report.reducer';
import { ReportService } from './Report.service';

const FETCH_BATCH = 5000;

const selectActiveTab = (state: { report: { activeTab: TabType } }): TabType => state.report.activeTab;

function* handleFetchReports() {
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

function* fetchHistoryRunSaga(action: PayloadAction<string>) {
  const runId = action.payload;
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

function* fetchMismatchesSaga(action: PayloadAction<string>) {
  const runId = action.payload;

  try {
    let offset = 0;
    const collected: MismatchSampleRow[] = [];
    let pageTotal = 0;

    for (let attempt = 0; attempt < 30; attempt += 1) {
      offset = 0;
      collected.length = 0;

      for (;;) {
        const page: import('../../shared/api/Api').ValidationMismatchesResponse = yield call(
          ReportService.fetchMismatchesPage,
          runId,
          { limit: FETCH_BATCH, offset },
        );
        pageTotal = page.total;
        collected.push(...page.items);
        yield put(reportActions.fetchMismatchesProgress({
          runId,
          items: [...collected],
          total: page.total,
          progressMessage: page.total > collected.length
            ? `Loaded ${collected.length.toLocaleString()} / ${page.total.toLocaleString()} mismatch rows…`
            : '',
        }));
        if (collected.length >= page.total && page.total > 0) break;
        if (page.items.length < FETCH_BATCH) break;
        offset += FETCH_BATCH;
      }

      if (collected.length > 0 || pageTotal > 0) break;

      yield put(reportActions.fetchMismatchesProgress({
        runId,
        items: [],
        total: 0,
        progressMessage: 'Waiting for mismatch rows to finish saving…',
      }));
      yield delay(2000);
    }

    yield put(reportActions.fetchMismatchesSuccess({
      runId,
      items: collected,
      total: pageTotal,
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
    takeLatest(reportActions.setTab.type, handleFetchReports),
    takeLatest(reportActions.fetchHistoryRunRequest.type, fetchHistoryRunSaga),
    takeLatest(reportActions.fetchMismatchesRequest.type, fetchMismatchesSaga),
  ]);
}
