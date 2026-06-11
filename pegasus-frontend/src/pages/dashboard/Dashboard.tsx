import React, { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { EntityCustomizer } from './components/EntityCustomizer';
import { ActiveTasksPanel } from './components/ActiveTasksPanel';
import { MetricsPanel } from './components/MetricsPanel';
import { PerformanceChartPanel } from './components/PerformanceChartPanel';
import { WorkspacesPanel } from './components/WorkspacesPanel';
import { dashboardActions } from './Dashboard.reducer';
import styles from './Dashboard.module.scss';

export const Dashboard: React.FC = () => {
  const dispatch = useAppDispatch();
  const { data, isFetching } = useAppSelector((state) => state.dashboard.dashboardDataState);

  useEffect(() => {
    dispatch(dashboardActions.fetchDashboardDataRequest());
  }, [dispatch]);

  return (
    <div className={styles.dashboardContainer}>
      <div className={styles.row1Grid}>
        <MetricsPanel
          runningCount={data?.runningTasksCount ?? 0}
          passed={data?.totals.passed ?? 0}
          failed={data?.totals.failed ?? 0}
          totalValidated={data?.totals.total ?? 0}
          isLoading={isFetching}
        />
        <PerformanceChartPanel dailyStats={data?.dailyStats ?? []} isLoading={isFetching} />
      </div>

      <div className={styles.row2Grid} style={{ alignItems: 'flex-start' }}>
        <ActiveTasksPanel tasks={data?.tasks ?? []} isLoading={isFetching} />
        <WorkspacesPanel entities={data?.entities ?? []} isLoading={isFetching} />
        <EntityCustomizer entities={data?.entities ?? []} />
      </div>
    </div>
  );
};

export default Dashboard;
