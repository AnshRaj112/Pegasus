import React, { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { MetricsPanel } from './components/MetricsPanel';
import { PerformanceChartPanel } from './components/PerformanceChartPanel';
import { dashboardActions } from './Dashboard.reducer';
import styles from './Dashboard.module.scss';

const Dashboard: React.FC = () => {
  const dispatch = useAppDispatch();
  const { data, isFetching } = useAppSelector((state) => state.dashboard.dashboardDataState);

  useEffect(() => {
    dispatch(dashboardActions.fetchDashboardDataRequest());
  }, [dispatch]);

  return (
    <div className={styles.dashboardContainer}>
      <PerformanceChartPanel dailyStats={data?.dailyStats ?? []} isLoading={isFetching} />
      <MetricsPanel
        runningCount={data?.runningTasksCount ?? 0}
        passed={data?.totals.passed ?? 0}
        failed={data?.totals.failed ?? 0}
        totalValidated={data?.totals.total ?? 0}
        isLoading={isFetching}
      />
    </div>
  );
};

export default Dashboard;
