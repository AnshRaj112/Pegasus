import React, { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { EntityCustomizer } from './components/EntityCustomizer';
import { ActiveTasksPanel } from './components/ActiveTasksPanel';
import { MetricsPanel } from './components/MetricsPanel';
import { PerformanceChartPanel } from './components/PerformanceChartPanel';
import { WorkspacesPanel } from './components/WorkspacesPanel';
import { dashboardActions } from './Dashboard.reducer';
import { MetricCard } from '../../components/ui/MetricCard';
import styles from './Dashboard.module.scss';

export const Dashboard: React.FC = () => {
  
  const chartLinesY = [0, 50, 100, 150, 200];
  const passDataPointsY = [180, 160, 170, 120, 130, 90, 100];

  // Wire up Redux
  const dispatch = useAppDispatch();
  const { data, isFetching } = useAppSelector((state) => state.dashboard.dashboardDataState);

  // Use Redux data if available, otherwise fallback to your hardcoded arrays for now
  const displayTasks = data?.tasks || [];
  const displayRunningCount = data?.runningTasksCount || 14;

  // Trigger the API call on mount
  useEffect(() => {
    dispatch(dashboardActions.fetchDashboardDataRequest());
  }, [dispatch]);

  return (
    <div className={styles.dashboardContainer}>
      {/* Row 1 Layout Panel Section */}
      <div className={styles.row1Grid}>
        <MetricsPanel runningCount={displayRunningCount} />
        <PerformanceChartPanel />
      </div>

      {/* Row 2 Secondary Content Splits Layout */}
      <div className={styles.row2Grid} style={{ alignItems: 'flex-start' }}>

        {/* Panel 1: Queue Task Processor Data View */}
        <ActiveTasksPanel tasks={displayTasks} />

        {/* Panel 2: Workspace Management Directory list */}
        <WorkspacesPanel />
            

        {/* Panel 3: Workspace Filtering Entity Selector Card Customizer */}
        <EntityCustomizer />
      </div>
    </div>
  );
};

export default Dashboard;