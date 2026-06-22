import React from 'react';
import { CheckCircle, XCircle, Database, RefreshCw } from 'lucide-react';

import { MetricCard } from '../../../components/ui/MetricCard';
import styles from '../Dashboard.module.scss';

interface MetricsPanelProps {
  runningCount: number;
  passed: number;
  failed: number;
  totalValidated: number;
  isLoading?: boolean;
}

export const MetricsPanel: React.FC<MetricsPanelProps> = ({
  runningCount,
  passed,
  failed,
  totalValidated,
  isLoading,
}) => {
  return (
    <div className={styles.leftMetricsCol}>
      <div className={styles.metricsSubGrid}>
        <MetricCard
          Icon={CheckCircle}
          iconColor="var(--status-pass)"
          label="Pass"
          value={isLoading ? '…' : passed.toLocaleString()}
          subtext="Last 7 days"
          subtextColor="var(--status-pass)"
        />
        <MetricCard
          Icon={XCircle}
          iconColor="var(--status-fail)"
          label="Fail"
          value={isLoading ? '…' : failed.toLocaleString()}
          subtext="Last 7 days"
          subtextColor="var(--status-fail)"
        />
        <MetricCard
          Icon={Database}
          iconColor="var(--color-midnight-green)"
          label="Total Validated"
          value={isLoading ? '…' : totalValidated.toLocaleString()}
          subtext="Completed runs"
        />
        <MetricCard
          Icon={RefreshCw}
          iconColor="#ea580c"
          label="Running"
          value={runningCount.toString()}
          subtext="Active processing tasks"
          isSpinning={runningCount > 0}
        />
      </div>
    </div>
  );
};
