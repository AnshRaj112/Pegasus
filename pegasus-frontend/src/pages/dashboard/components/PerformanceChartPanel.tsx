import React, { useMemo } from 'react';

import { DailyStatRow } from '../../../shared/api/Api';
import styles from '../Dashboard.module.scss';

interface PerformanceChartPanelProps {
  dailyStats: DailyStatRow[];
  isLoading?: boolean;
}

const formatDayLabel = (dateStr: string): string => {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { weekday: 'short' });
};

export const PerformanceChartPanel: React.FC<PerformanceChartPanelProps> = ({ dailyStats, isLoading }) => {
  const { passPoints, failPoints, labels, maxVal } = useMemo(() => {
    const items = dailyStats.slice(-7);
    const max = Math.max(1, ...items.flatMap((i) => [i.passed, i.failed]));
    const scaleY = (v: number) => 180 - (v / max) * 160;
    return {
      passPoints: items.map((i) => scaleY(i.passed)),
      failPoints: items.map((i) => scaleY(i.failed)),
      labels: items.map((i) => formatDayLabel(i.date)),
      maxVal: max,
    };
  }, [dailyStats]);

  const chartLinesY = [0, maxVal * 0.25, maxVal * 0.5, maxVal * 0.75, maxVal].map((v) =>
    180 - (v / Math.max(1, maxVal)) * 160,
  );

  const toPath = (points: number[]) =>
    points.map((y, i) => `${i === 0 ? 'M' : 'L'}${(i / Math.max(1, points.length - 1)) * 800},${y}`).join(' ');

  return (
    <div className={styles.rightChartCol}>
      <div className={styles.chartHeader}>
        <div>
          <h3 className={styles.chartTitle}>
            Validation Performance
          </h3>
          <p className={styles.chartSubtitle}>
            {isLoading ? 'Loading…' : 'Pass vs fail (last 7 days)'}
          </p>
        </div>
        <div className={styles.chartLegend}>
          <div className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.legendDotPass}`} />
            Pass
          </div>
          <div className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.legendDotFail}`} />
            Fail
          </div>
        </div>
      </div>

      <div className={styles.chartWrapper}>
        {dailyStats.length === 0 && !isLoading ? (
          <p className={styles.chartEmpty}>
            No validation history yet. Run a validation to see trends.
          </p>
        ) : (
          <svg className={styles.chartSvg} viewBox="0 0 800 200" preserveAspectRatio="none">
            <defs>
              <linearGradient id="grad-pass" x1="0%" x2="0%" y1="0%" y2="100%">
                <stop offset="0%" stopColor="var(--color-midnight-green)" stopOpacity={0.2} />
                <stop offset="100%" stopColor="var(--color-midnight-green)" stopOpacity={0} />
              </linearGradient>
            </defs>
            {chartLinesY.map((y) => (
              <line key={y} className={styles.chartGridLine} x1="0" x2="800" y1={y} y2={y} />
            ))}
            {passPoints.length > 1 && (
              <>
                <path
                  d={`${toPath(passPoints)} L800,200 L0,200 Z`}
                  fill="url(#grad-pass)"
                />
                <path
                  d={toPath(passPoints)}
                  className={styles.chartPassLine}
                />
              </>
            )}
            {failPoints.length > 1 && (
              <path
                d={toPath(failPoints)}
                className={styles.chartFailLine}
              />
            )}
          </svg>
        )}
        <div className={styles.chartDaysLabel}>
          {(labels.length ? labels : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']).map((l) => (
            <span key={l}>{l}</span>
          ))}
        </div>
      </div>
    </div>
  );
};
