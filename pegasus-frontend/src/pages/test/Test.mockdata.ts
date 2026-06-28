import { AxiosError, AxiosHeaders } from 'axios'

import { initializeEmptyState } from '~/shared/constants/common.constants'

import { TestEntity } from './Test.interface'
import { initialState } from './Test.reducer'

export const mockActiveTests: TestEntity[] = [
  {
    id: '1',
    title: 'EMPLOYEES',
    subtitle: 'ID: TC-8842-EMP-PROD',
    schedule: 'Every 1 hr(s)',
    type: 'F',
    nextRun: 'Running',
  },
  {
    id: '2',
    title: 'SALES_DATA_V4',
    subtitle: 'ID: TC-9901-SALES-AGG',
    schedule: 'Once on 2026-05-15',
    type: 'L',
    nextRun: 'Scheduled',
  },
  {
    id: '3',
    title: 'INVENTORY_SNAPSHOT',
    subtitle: 'ID: TC-4412-INV-SYNC',
    schedule: 'Every 12 hr(s)',
    type: 'F+',
    nextRun: 'Running',
  }
];

export const mockCompletedTests: TestEntity[] = [
  {
    id: '101',
    title: 'transaction_log_validation',
    subtitle: 'ID: TEST-9921',
    schedule: 'Every 1 hr(s)',
    type: 'F+',
    status: 'Completed',
    result: 'Pass',
    duration: '14 sec',
    endedDate: "Jun 26 '26",
    endedTime: '18:00:00',
  },
  {
    id: '102',
    title: 'customer_integrity_check',
    subtitle: 'ID: TEST-9844',
    schedule: 'Daily at 00:00',
    type: 'L',
    status: 'Completed',
    result: 'Fail',
    duration: '22 sec',
    endedDate: "Jun 26 '26",
    endedTime: '17:00:00',
  },
  {
    id: '103',
    title: 'schema_drift_detection',
    subtitle: 'ID: TEST-9712',
    schedule: 'Manual Run',
    type: 'L',
    status: 'Incoherent',
    duration: '08 sec',
    endedDate: "Jun 26 '26",
    endedTime: '16:30:00',
  }
];

export const mockSavedTests: TestEntity[] = [
  {
    id: '201',
    title: 'Standard Load Performance Analysis',
    subtitle: 'ID: TST-2024-089-V2',
    schedule: 'Ref: EMEA_Q4_Optimization',
    type: 'F',
    isDraft: true,
  },
  {
    id: '202',
    title: 'Cloud Latency Stress Test (B)',
    subtitle: 'ID: TST-2024-112-ST',
    schedule: 'Scheduled for next maintenance window',
    type: 'F',
    isDraft: true,
  }
];

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
    data: { message: 'Failed to load active tests.' },
  },
)

export const activeTestsLoading = {
  ...initializeEmptyState,
  isFetching: true,
  error: null,
}

export const activeTestsSuccess = {
  ...initializeEmptyState,
  data: mockActiveTests,
  isFetching: false,
  error: null,
}

export const activeTestsError = {
  ...initializeEmptyState,
  isFetching: false,
  error: 'Failed to load active tests.',
}

export const completedTestsSuccess = {
  ...initializeEmptyState,
  data: mockCompletedTests,
  isFetching: false,
  error: null,
}

export const savedTestsSuccess = {
  ...initializeEmptyState,
  data: mockSavedTests,
  isFetching: false,
  error: null,
}

export const testStateWithActiveData = {
  ...initialState,
  activeTests: activeTestsSuccess,
}