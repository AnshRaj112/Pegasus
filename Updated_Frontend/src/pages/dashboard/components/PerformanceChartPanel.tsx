import React from 'react';
import styles from '../Dashboard.module.scss';

export const PerformanceChartPanel: React.FC = () => {
  const chartLinesY = [0, 50, 100, 150, 200];
  const passDataPointsY = [180, 160, 170, 120, 130, 90, 100];

  return (
    <div className={styles.rightChartCol}>
      <div className={styles.chartHeader}>
        <div>
          <h3 style={{ fontFamily: 'var(--font-h3)', fontSize: 'var(--h3)', margin: 0, color: 'var(--on-surface)' }}>Validation Performance</h3>
          <p style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)', margin: '4px 0 0' }}>Historical analysis of data integrity scores (Last 7 Days)</p>
        </div>
        <div className={styles.chartLegend}>
          <div className={styles.legendItem}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--primary)' }}></span>Pass
          </div>
          <div className={styles.legendItem}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--error)' }}></span>Fail
          </div>
        </div>
      </div>

      <div className={styles.chartWrapper}>
        <svg style={{ width: '100%', height: '100%' }} viewBox="0 0 800 200" preserveAspectRatio="none">
          <defs>
            <linearGradient id="grad-pass" x1="0%" x2="0%" y1="0%" y2="100%">
              <stop offset="0%" style={{ stopColor: 'var(--primary)', stopOpacity: 0.2 }}></stop>
              <stop offset="100%" style={{ stopColor: 'var(--primary)', stopOpacity: 0 }}></stop>
            </linearGradient>
          </defs>
          {chartLinesY.map(y => (
            <line key={y} stroke="#f0f0f0" strokeWidth="1" x1="0" x2="800" y1={y} y2={y}></line>
          ))}
          <path d="M0,180 L133,160 L266,170 L400,120 L533,130 L666,90 L800,100 L800,200 L0,200 Z" fill="url(#grad-pass)"></path>
          <path d="M0,180 L133,160 L266,170 L400,120 L533,130 L666,90 L800,100" fill="none" stroke="#0057c2" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3"></path>
          <path d="M0,195 L133,190 L266,192 L400,185 L533,188 L666,182 L800,186" fill="none" stroke="#ba1a1a" strokeDasharray="4" strokeLinecap="round" strokeWidth="2"></path>
          {passDataPointsY.map((y, i) => (
            <circle key={i} cx={i * 133.33} cy={y} r="4" fill="#0057c2" />
          ))}
        </svg>
        <div className={styles.chartDaysLabel}>
          <span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span>
        </div>
      </div>
    </div>
  );
};