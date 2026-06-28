import React from 'react';
import type { LucideIcon } from 'lucide-react';
import styles from './MetricCard.module.scss';

type MetricVariant = 'pass' | 'fail' | 'total' | 'running';

interface MetricCardProps {
  Icon: LucideIcon;
  variant: MetricVariant;
  label: string;
  value: string;
  subtext: string;
  isSpinning?: boolean;
}

const variantClass: Record<MetricVariant, string> = {
  pass: styles.variantPass,
  fail: styles.variantFail,
  total: styles.variantTotal,
  running: styles.variantRunning,
};

export const MetricCard: React.FC<MetricCardProps> = ({
  Icon,
  variant,
  label,
  value,
  subtext,
  isSpinning = false,
}) => {
  return (
    <div className={`${styles.card} ${variantClass[variant]}`}>
      <div className={styles.header}>
        <Icon
          size={18}
          className={`${styles.icon} ${isSpinning ? 'icon-spin-loop' : ''}`}
        />
        <span className={styles.label}>{label}</span>
      </div>
      <div className={styles.body}>
        <span className={styles.value}>{value}</span>
        <div className={styles.subtext}>{subtext}</div>
      </div>
    </div>
  );
};
