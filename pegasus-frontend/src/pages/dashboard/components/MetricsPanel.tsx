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
          variant="pass"
          label="Pass"
          value={isLoading ? '…' : passed.toLocaleString()}
          subtext="Last 7 days"
        />
        <MetricCard
          Icon={XCircle}
          variant="fail"
          label="Fail"
          value={isLoading ? '…' : failed.toLocaleString()}
          subtext="Last 7 days"
        />
        <MetricCard
          Icon={Database}
          variant="total"
          label="Total Validated"
          value={isLoading ? '…' : totalValidated.toLocaleString()}
          subtext="Completed runs"
        />
        <MetricCard
          Icon={RefreshCw}
          variant="running"
          label="Running"
          value={runningCount.toString()}
          subtext="Active processing tasks"
          isSpinning={runningCount > 0}
        />
      </div>
    </div>
  );
};
