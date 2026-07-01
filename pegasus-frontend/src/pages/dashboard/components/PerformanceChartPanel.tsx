import React, { useMemo, useState } from 'react';

import { DailyStatRow } from '../../../shared/api/Api';
import { monotoneCurvePath } from '../utils/monotoneCurvePath';
import styles from '../Dashboard.module.scss';

interface PerformanceChartPanelProps {
  dailyStats: DailyStatRow[];
  isLoading?: boolean;
}

const formatDayLabel = (dateStr: string): string => {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { weekday: 'short' });
};

const formatTooltipDate = (dateStr: string): string => {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
};

export const PerformanceChartPanel: React.FC<PerformanceChartPanelProps> = ({ dailyStats, isLoading }) => {
  const [hoveredDayIndex, setHoveredDayIndex] = useState<number | null>(null);
  const [hoveredLine, setHoveredLine] = useState<'pass' | 'fail' | null>(null);

  const items = useMemo(() => dailyStats.slice(-7), [dailyStats]);

  const maxVal = useMemo(() => {
    return Math.max(1, ...items.flatMap((i) => [i.passed, i.failed]));
  }, [items]);

  // Coordinate mapping based on viewBox="0 0 850 350"
  // x range: 60 to 800 (width 740)
  // y range: 30 to 300 (height 270)
  const scaleX = (index: number) => 60 + (index / Math.max(1, items.length - 1)) * 740;
  const scaleY = (v: number) => 300 - (v / maxVal) * 270;

  const { passPoints, failPoints, labels } = useMemo(() => {
    return {
      passPoints: items.map((item, idx) => ({ x: scaleX(idx), value: item.passed })),
      failPoints: items.map((item, idx) => ({ x: scaleX(idx), value: item.failed })),
      labels: items.map((item) => formatDayLabel(item.date)),
    };
  }, [items]);

  const isPassAllZero = useMemo(() => items.every((i) => i.passed === 0), [items]);
  const isFailAllZero = useMemo(() => items.every((i) => i.failed === 0), [items]);

  const passLineClass = `${styles.chartPassLine} ${
    hoveredLine === 'pass'
      ? styles.chartLineHighlighted
      : hoveredLine === 'fail'
      ? styles.chartLineDimmed
      : ''
  }`;

  const failLineClass = `${styles.chartFailLine} ${
    hoveredLine === 'fail'
      ? styles.chartLineHighlighted
      : hoveredLine === 'pass'
      ? styles.chartLineDimmed
      : ''
  }`;

  const rectWidth = items.length > 1 ? 740 / (items.length - 1) : 740;

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
          <div
            className={`${styles.legendItem} ${isPassAllZero ? styles.legendItemDisabled : ''}`}
            onMouseEnter={() => {
              if (!isPassAllZero) setHoveredLine('pass');
            }}
            onMouseLeave={() => setHoveredLine(null)}
          >
            <span className={`${styles.legendDot} ${styles.legendDotPass}`} />
            Pass
          </div>
          <div
            className={`${styles.legendItem} ${isFailAllZero ? styles.legendItemDisabled : ''}`}
            onMouseEnter={() => {
              if (!isFailAllZero) setHoveredLine('fail');
            }}
            onMouseLeave={() => setHoveredLine(null)}
          >
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
          <>
            <svg className={styles.chartSvg} viewBox="0 0 850 320" preserveAspectRatio="none">
              <defs>
                <linearGradient id="grad-pass" x1="0%" x2="0%" y1="0%" y2="100%">
                  <stop offset="0%" stopColor="var(--status-pass)" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="var(--status-pass)" stopOpacity={0} />
                </linearGradient>
                {/* Clips all chart content strictly within the plot area */}
                <clipPath id="plot-area-clip">
                  <rect x="60" y="28" width="755" height="275" />
                </clipPath>
              </defs>

              {/* Grid lines only — Y labels are rendered as HTML below */}
              {[0, maxVal * 0.25, maxVal * 0.5, maxVal * 0.75, maxVal].map((v) => {
                const y = scaleY(v);
                return (
                  <line key={v} className={styles.chartGridLine} x1="60" x2="810" y1={y} y2={y} />
                );
              })}

              {/* Vertical hover guide line */}
              {hoveredDayIndex !== null && (
                <line
                  className={styles.chartGuideLine}
                  x1={scaleX(hoveredDayIndex)}
                  y1={20}
                  x2={scaleX(hoveredDayIndex)}
                  y2={300}
                />
              )}

              {/* All chart drawings clipped to plot bounds — prevents bezier overshoot */}
              <g clipPath="url(#plot-area-clip)">

                {/* Pass area fill */}
                {passPoints.length > 1 && (
                  <>
                    <path
                      d={`${monotoneCurvePath(passPoints, scaleY)} L${scaleX(items.length - 1)},300 L60,300 Z`}
                      fill="url(#grad-pass)"
                      style={{
                        opacity: hoveredLine === 'fail' ? 0.15 : 1,
                        transition: 'opacity 0.2s ease',
                      }}
                    />
                    <path d={monotoneCurvePath(passPoints, scaleY)} className={passLineClass} />
                  </>
                )}

                {/* Fail line */}
                {failPoints.length > 1 && (
                  <path d={monotoneCurvePath(failPoints, scaleY)} className={failLineClass} />
                )}

                {/* Pass data-point markers */}
                {passPoints.map((pt, idx) => (
                  <circle
                    key={`pass-marker-${idx}`}
                    cx={pt.x}
                    cy={scaleY(pt.value)}
                    r={hoveredDayIndex === idx ? 6 : 4}
                    fill="var(--status-pass)"
                    stroke="var(--surface-container-lowest)"
                    strokeWidth={hoveredDayIndex === idx ? 2 : 1.5}
                    className={styles.chartMarker}
                    style={{ opacity: hoveredLine === 'fail' ? 0.15 : 1 }}
                  />
                ))}

                {/* Fail data-point markers */}
                {failPoints.map((pt, idx) => (
                  <circle
                    key={`fail-marker-${idx}`}
                    cx={pt.x}
                    cy={scaleY(pt.value)}
                    r={hoveredDayIndex === idx ? 6 : 4}
                    fill="var(--status-fail)"
                    stroke="var(--surface-container-lowest)"
                    strokeWidth={hoveredDayIndex === idx ? 2 : 1.5}
                    className={styles.chartMarker}
                    style={{ opacity: hoveredLine === 'pass' ? 0.15 : 1 }}
                  />
                ))}

              </g>

              {/* Invisible hover zones per day column */}
              {items.map((_, idx) => (
                <rect
                  key={`hover-zone-${idx}`}
                  x={scaleX(idx) - rectWidth / 2}
                  y={20}
                  width={rectWidth}
                  height={280}
                  fill="transparent"
                  style={{ cursor: 'crosshair' }}
                  onMouseEnter={() => setHoveredDayIndex(idx)}
                  onMouseLeave={() => setHoveredDayIndex(null)}
                />
              ))}
            </svg>

            {/* ── Y-axis labels: HTML spans absolutely positioned in the SVG left gutter ── */}
            {[0, maxVal * 0.25, maxVal * 0.5, maxVal * 0.75, maxVal].map((v) => {
              // scaleY maps v → SVG coord; divide by 320 (viewBox height) for % of chartWrapper
              const topPct = (scaleY(v) / 320) * 100;
              return (
                <span
                  key={v}
                  className={styles.chartYLabel}
                  style={{ top: `${topPct}%` }}
                >
                  {Math.round(v).toLocaleString()}
                </span>
              );
            })}

            {/* ── Day labels — HTML row outside SVG for clean, easy-to-control spacing ── */}
            <div className={styles.chartAxisLabels}>
              {(labels.length ? labels : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']).map((l, idx) => (
                <span
                  key={l + idx}
                  className={`${styles.chartAxisLabel} ${hoveredDayIndex === idx ? styles.chartAxisLabelActive : ''}`}
                >
                  {l}
                </span>
              ))}
            </div>

            {/* Hover Tooltip display */}
            {hoveredDayIndex !== null && items[hoveredDayIndex] && (
              <div
                className={styles.chartTooltip}
                style={{
                  left: hoveredDayIndex > 3
                    ? `calc(${(scaleX(hoveredDayIndex) / 850) * 100}% - 160px)`
                    : `calc(${(scaleX(hoveredDayIndex) / 850) * 100}% + 20px)`,
                  top: '20px',
                }}
              >
                <div className={styles.tooltipDate}>
                  {formatTooltipDate(items[hoveredDayIndex].date)}
                </div>
                <div className={styles.tooltipRow}>
                  <span className={styles.tooltipPassDot} />
                  Pass: <strong>{items[hoveredDayIndex].passed}</strong>
                </div>
                <div className={styles.tooltipRow}>
                  <span className={styles.tooltipFailDot} />
                  Fail: <strong>{items[hoveredDayIndex].failed}</strong>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
