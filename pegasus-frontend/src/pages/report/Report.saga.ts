import { call, put, select, takeLatest } from 'redux-saga/effects';
import { reportActions } from './Report.reducer';
import { ReportService } from './Report.service';
import { TabType, ReportItem } from './Report.interface';

// Quick selector to check the current tab
const selectActiveTab = (state: any): TabType => state.report.activeTab;

function* handleFetchReports() {
  try {
    const activeTab: TabType = yield select(selectActiveTab);
    let data: ReportItem[] = [];

    if (activeTab === 'Active') {
      data = yield call(ReportService.fetchActive);
    } else if (activeTab === 'Completed') {
      data = yield call(ReportService.fetchCompleted);
    } else if (activeTab === 'Saved') {
      data = yield call(ReportService.fetchSaved);
    }

    yield put(reportActions.fetchReportsSuccess({ tab: activeTab, data }));
  } catch (error: any) {
    yield put(reportActions.fetchReportsFailure(error.message || 'Failed to fetch reports'));
  }
}

export function* reportSaga() {
  yield takeLatest(reportActions.fetchReportsRequest.type, handleFetchReports);
  yield takeLatest(reportActions.setTab.type, handleFetchReports);
}