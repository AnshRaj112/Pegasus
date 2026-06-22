import React, { useMemo } from 'react';

import type { DailyStatRow } from '../../../shared/api/Api';
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
          <h3 style={{ fontFamily: 'var(--font-h3)', fontSize: 'var(--h3)', margin: 0, color: 'var(--on-surface)' }}>
            Validation Performance
          </h3>
          <p style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)', margin: '4px 0 0' }}>
            {isLoading ? 'Loading…' : 'Pass vs fail (last 7 days)'}
          </p>
        </div>
        <div className={styles.chartLegend}>
          <div className={styles.legendItem}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--color-midnight-green)' }} />
            Pass
          </div>
          <div className={styles.legendItem}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--status-fail)' }} />
            Fail
          </div>
        </div>
      </div>

      <div className={styles.chartWrapper}>
        {dailyStats.length === 0 && !isLoading ? (
          <p style={{ padding: '24px', color: 'var(--on-surface-variant)', fontSize: '13px' }}>
            No validation history yet. Run a validation to see trends.
          </p>
        ) : (
          <svg style={{ width: '100%', height: '100%' }} viewBox="0 0 800 200" preserveAspectRatio="none">
            <defs>
              <linearGradient id="grad-pass" x1="0%" x2="0%" y1="0%" y2="100%">
                <stop offset="0%" style={{ stopColor: 'var(--color-midnight-green)', stopOpacity: 0.2 }} />
                <stop offset="100%" style={{ stopColor: 'var(--color-midnight-green)', stopOpacity: 0 }} />
              </linearGradient>
            </defs>
            {chartLinesY.map((y) => (
              <line key={y} stroke="#f0f0f0" strokeWidth="1" x1="0" x2="800" y1={y} y2={y} />
            ))}
            {passPoints.length > 1 && (
              <>
                <path
                  d={`${toPath(passPoints)} L800,200 L0,200 Z`}
                  fill="url(#grad-pass)"
                />
                <path
                  d={toPath(passPoints)}
                  fill="none"
                  stroke="#234B5F"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="3"
                />
              </>
            )}
            {failPoints.length > 1 && (
              <path
                d={toPath(failPoints)}
                fill="none"
                stroke="#ba1a1a"
                strokeDasharray="4"
                strokeLinecap="round"
                strokeWidth="2"
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
