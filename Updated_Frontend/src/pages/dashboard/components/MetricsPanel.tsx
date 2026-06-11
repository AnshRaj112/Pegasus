import React from 'react';
import { CheckCircle, XCircle, Database, RefreshCw } from 'lucide-react';

import { MetricCard } from '../../../components/ui/MetricCard';
import styles from '../Dashboard.module.scss';

interface MetricsPanelProps {
  runningCount: number;
}

export const MetricsPanel: React.FC<MetricsPanelProps> = ({ runningCount }) => {
  return (
    <div className={styles.leftMetricsCol}>
      <div className={styles.metricsSubGrid}>
        <MetricCard Icon={CheckCircle} iconColor="#16a34a" label="Pass" value="1,248" subtext="+12% vs last week" subtextColor="#16a34a" />
        <MetricCard Icon={XCircle} iconColor="var(--error)" label="Fail" value="42" subtext="-4% vs last week" subtextColor="var(--error)" />
        <MetricCard Icon={Database} iconColor="var(--primary)" label="Total Validated" value="1.8M" subtext="Records across all files" />
        <MetricCard Icon={RefreshCw} iconColor="#ea580c" label="Running" value={runningCount.toString()} subtext="Active processing tasks" isSpinning={true} />
      </div>
    </div>
  );
};