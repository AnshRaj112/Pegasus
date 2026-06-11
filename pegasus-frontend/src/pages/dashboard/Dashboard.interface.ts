import type { DailyStatRow, EntityInsight } from '../../shared/api/Api';

export interface TaskItem {
  id: string;
  name: string;
  time: string;
  status: 'Completed' | 'Running' | 'Scheduled' | 'Failed';
  progress: number;
}

export interface DashboardDataResponse {
  tasks: TaskItem[];
  runningTasksCount: number;
  dailyStats: DailyStatRow[];
  totals: { passed: number; failed: number; total: number };
  entities: EntityInsight[];
}

export interface DashboardReducerState {
  dashboardDataState: {
    data: DashboardDataResponse | null;
    isFetching: boolean;
    error: string | null;
  };
}
