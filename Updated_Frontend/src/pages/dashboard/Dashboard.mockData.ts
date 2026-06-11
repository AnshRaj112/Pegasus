import { type DashboardDataResponse } from './Dashboard.interface';

export const mockDashboardData: DashboardDataResponse = {
  runningTasksCount: 14,
  tasks: [
    { id: '1', name: 'GL_Sync_0924', time: '2 mins ago', status: 'Completed', progress: 100 },
    { id: '2', name: 'Payroll_Verify_Q3', time: 'Running...', status: 'Running', progress: 64 },
    { id: '3', name: 'Risk_Model_F2F', time: 'Scheduled: 14:00', status: 'Scheduled', progress: 0 },
    { id: '4', name: 'Customer_360_Master', time: '1 hour ago', status: 'Failed', progress: 42 }
  ]
};