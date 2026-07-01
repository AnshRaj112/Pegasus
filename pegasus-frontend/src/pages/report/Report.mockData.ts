import { AxiosError, AxiosHeaders } from 'axios'

import { initializeEmptyState } from '~/shared/constants/common.constants'
import type { MismatchSampleRow, ValidationHistoryDetail } from '~/shared/api/Api'

import { ReportItem, TabType } from './Report.interface'
import { initialState } from './Report.reducer'

export const mockActiveReport: ReportItem = {
  id: 'pair-1',
  sourcePath: '/data/source.csv',
  targetPath: '/data/target.csv',
  sourceTitle: 'source.csv',
  sourceSubtitle: '/data/source.csv',
  jobTitle: 'target.csv',
  jobSubtitle: 'Validating…',
  badges: [{ type: 'text', content: 'Running' }],
  latestRunId: 'run-active-1',
  latestIsMatch: null,
  jobId: 'job-active-1',
}

export const mockCompletedReport: ReportItem = {
  id: '1',
  sourcePath: '/data/completed-source.csv',
  targetPath: '/data/completed-target.csv',
  sourceTitle: 'completed-source.csv',
  sourceSubtitle: '/data/completed-source.csv',
  jobTitle: 'completed-target.csv',
  jobSubtitle: 'Latest: Jun 12, 26',
  badges: [
    { type: 'text', content: 'Jun 12, 26' },
    { type: 'box', content: 'P' },
    { type: 'box', content: 'F' },
    { type: 'box', content: 'P' },
  ],
  latestRunId: 'run-completed-1',
  latestIsMatch: true,
}

export const mockSavedReport: ReportItem = {
  id: 'saved-pair-1',
  sourcePath: '/data/saved-source.csv',
  targetPath: '/data/saved-target.csv',
  sourceTitle: 'saved-source.csv',
  sourceSubtitle: '/data/saved-source.csv',
  jobTitle: 'saved-target.csv',
  jobSubtitle: 'Jun 10, 26',
  badges: [{ type: 'icon', content: 'draft-icon' }],
  latestRunId: 'run-saved-1',
  latestIsMatch: null,
  draftRunId: 'run-saved-1',
}

export const mockHistoryRunDetail: ValidationHistoryDetail = {
  run_id: 'run-completed-1',
  status: 'completed',
  source_path: '/data/completed-source.csv',
  target_path: '/data/completed-target.csv',
  source_filename: 'completed-source.csv',
  target_filename: 'completed-target.csv',
  uid_column: 'id',
  delimiter: ',',
  is_match: true,
  mismatch_counts: { missing_in_target: 0, extra_in_target: 0, value_mismatch: 0 },
  mapping_count: 5,
  created_at: '2026-06-12T10:00:00.000Z',
  completed_at: '2026-06-12T10:05:00.000Z',
  compared_column_count: 5,
  compared_columns: ['id', 'name', 'amount'],
}

export const mockMismatchRow: MismatchSampleRow = {
  uid: 'row-1',
  mismatch_type: 'value_mismatch',
  column_name: 'amount',
  source_value: '100',
  target_value: '101',
}

export const mockAxiosError = new AxiosError(
  'Server error',
  'ERR_BAD_REQUEST',
  undefined,
  undefined,
  {
    status: 500,
    statusText: 'Internal Server Error',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: { message: 'Failed to fetch reports' },
  },
)

export const activeReportsLoading = {
  ...initializeEmptyState,
  isFetching: true,
  error: null,
}

export const activeReportsSuccess = {
  ...initializeEmptyState,
  data: [mockActiveReport],
  isFetching: false,
  error: null,
}

export const activeReportsError = {
  ...initializeEmptyState,
  isFetching: false,
  error: 'Failed to fetch reports',
}

export const completedReportsSuccess = {
  ...initializeEmptyState,
  data: [mockCompletedReport],
  isFetching: false,
  error: null,
}

export const savedReportsSuccess = {
  ...initializeEmptyState,
  data: [mockSavedReport],
  isFetching: false,
  error: null,
}

export const reportStateWithActiveData = {
  ...initialState,
  activeReports: activeReportsSuccess,
}

export const reportStateWithCompletedData = {
  ...initialState,
  activeTab: 'Completed' as TabType,
  completedReports: completedReportsSuccess,
}

export const historyRunLoading = {
  runId: 'run-completed-1',
  data: null,
  isFetching: true,
  error: null,
}

export const historyRunSuccess = {
  runId: 'run-completed-1',
  data: mockHistoryRunDetail,
  isFetching: false,
  error: null,
}

export const mismatchesLoading = {
  runId: 'run-completed-1',
  items: [],
  total: 0,
  isFetching: true,
  isComplete: false,
  progressMessage: 'Loading mismatch rows…',
  error: null,
}

export const mismatchesSuccess = {
  runId: 'run-completed-1',
  items: [mockMismatchRow],
  total: 1,
  isFetching: false,
  isComplete: true,
  progressMessage: '',
  error: null,
}
