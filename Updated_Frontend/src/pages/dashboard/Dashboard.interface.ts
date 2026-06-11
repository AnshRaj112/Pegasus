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
}

export interface DashboardReducerState {
  dashboardDataState: {
    data: DashboardDataResponse | null;
    isFetching: boolean;
    error: string | null;
  };
}