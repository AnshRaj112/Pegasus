import { type DashboardDataResponse } from './Dashboard.interface';

export const mockDashboardData: DashboardDataResponse = {
  runningTasksCount: 0,
  tasks: [],
  dailyStats: [],
  totals: { passed: 0, failed: 0, total: 0 },
  entities: [],
};
