import { AxiosError, AxiosHeaders } from 'axios'

import { initializeNullState } from '~/shared/constants/common.constants'

import { DashboardDataResponse, TaskItem } from './Dashboard.interface'
import { initialState } from './Dashboard.reducer'

export const mockTaskItem: TaskItem = {
  id: 'job-abc12345',
  name: 'Validation job-abc1',
  time: '5 mins ago',
  status: 'Running',
  progress: 50,
}

export const mockCompletedTask: TaskItem = {
  id: 'job-def67890',
  name: 'Validation job-def6',
  time: '2 hours ago',
  status: 'Completed',
  progress: 100,
}

export const mockEntityInsight = {
  inferred_entity: 'acme-corp',
  display_name: 'Acme Corp',
  confidence: 'high',
  success_count: 80,
  failed_count: 20,
  total_count: 100,
}

export const mockEntityInsightBeta = {
  inferred_entity: 'beta-inc',
  display_name: 'Beta Inc',
  confidence: 'medium',
  success_count: 5,
  failed_count: 5,
  total_count: 10,
}

export const mockDailyStats = [
  { date: '2026-06-22', passed: 120, failed: 8, total: 128 },
  { date: '2026-06-23', passed: 95, failed: 12, total: 107 },
  { date: '2026-06-24', passed: 140, failed: 5, total: 145 },
]

export const mockDashboardData: DashboardDataResponse = {
  runningTasksCount: 1,
  tasks: [mockTaskItem, mockCompletedTask],
  dailyStats: mockDailyStats,
  totals: { passed: 355, failed: 25, total: 380 },
  entities: [mockEntityInsight, mockEntityInsightBeta],
}

export const mockEmptyDashboardData: DashboardDataResponse = {
  runningTasksCount: 0,
  tasks: [],
  dailyStats: [],
  totals: { passed: 0, failed: 0, total: 0 },
  entities: [],
}

export const mockCreateEntityPayload = {
  display_name: 'New Entity',
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
    data: { message: 'Failed to fetch dashboard data' },
  },
)

export const dashboardDataLoading = {
  ...initialState,
  dashboardDataState: {
    ...initializeNullState,
    isFetching: true,
  },
}

export const dashboardDataSuccess = {
  ...initialState,
  dashboardDataState: {
    ...initializeNullState,
    data: mockDashboardData,
  },
}

export const dashboardDataError = {
  ...initialState,
  dashboardDataState: {
    ...initializeNullState,
    error: 'Failed to fetch dashboard data',
  },
}

export const createEntityLoading = {
  ...dashboardDataSuccess,
  createEntityState: {
    ...initializeNullState,
    isFetching: true,
  },
}

export const createEntitySuccess = {
  ...dashboardDataSuccess,
  createEntityState: {
    ...initializeNullState,
    data: 'Entity "New Entity" saved',
  },
}

export const createEntityError = {
  ...dashboardDataSuccess,
  createEntityState: {
    ...initializeNullState,
    error: 'Could not save entity (persistence may be disabled)',
  },
}
