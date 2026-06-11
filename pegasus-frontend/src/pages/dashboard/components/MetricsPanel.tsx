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
          iconColor="#16a34a"
          label="Pass"
          value={isLoading ? '…' : passed.toLocaleString()}
          subtext="Last 7 days"
          subtextColor="#16a34a"
        />
        <MetricCard
          Icon={XCircle}
          iconColor="var(--error)"
          label="Fail"
          value={isLoading ? '…' : failed.toLocaleString()}
          subtext="Last 7 days"
          subtextColor="var(--error)"
        />
        <MetricCard
          Icon={Database}
          iconColor="var(--primary)"
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
