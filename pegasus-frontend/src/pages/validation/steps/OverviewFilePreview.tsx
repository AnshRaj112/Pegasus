import React, { useMemo, useRef } from 'react';
import { Modal } from 'antd';
import { DatabaseOutlined, FileTextOutlined } from '@ant-design/icons';
import { LocalColumnPreviewResponse } from '../../../shared/api/Api';
import styles from './OverviewFilePreview.module.scss';

type SkeletonWidth = 'w40' | 'w45' | 'w55' | 'w65' | 'w70' | 'w75';

const skeletonWidthClass: Record<SkeletonWidth, string> = {
  w40: styles.skeletonW40,
  w45: styles.skeletonW45,
  w55: styles.skeletonW55,
  w65: styles.skeletonW65,
  w70: styles.skeletonW70,
  w75: styles.skeletonW75,
};

const headerSkeletonWidths: SkeletonWidth[] = ['w40', 'w55', 'w70'];

const cellSkeletonWidth = (rowIndex: number, colIndex: number): SkeletonWidth => {
  const widths: SkeletonWidth[] = ['w45', 'w55', 'w65', 'w75'];
  return widths[(rowIndex + colIndex) % 4];
};

const SkeletonCell: React.FC<{ width: SkeletonWidth }> = ({ width }) => (
  <div className={`${styles.skeletonCell} ${skeletonWidthClass[width]}`} />
);

const buildDataRows = (
  columns: string[],
  samples: Record<string, string[]>,
  rowCount: number,
): string[][] =>
  Array.from({ length: rowCount }, (_, rowIndex) =>
    columns.map((col) => {
      const value = samples[col]?.[rowIndex];
      return value != null && value !== '' ? value : '—';
    }),
  );

const maxSampleRows = (
  columns: string[],
  samples: Record<string, string[]>,
): number =>
  columns.reduce((max, col) => Math.max(max, samples[col]?.length ?? 0), 0);

const MAX_RENDER_COLUMNS = 50;

const capColumns = (columns: string[]): { visible: string[]; hiddenCount: number } => {
  if (columns.length <= MAX_RENDER_COLUMNS) {
    return { visible: columns, hiddenCount: 0 };
  }
  return { visible: columns.slice(0, MAX_RENDER_COLUMNS), hiddenCount: columns.length - MAX_RENDER_COLUMNS };
};

type OverviewFilePreviewProps = {
  open: boolean;
  preview: LocalColumnPreviewResponse | null;
  sourceLabel: string;
  targetLabel: string;
  loading: boolean;
  error: string | null;
  onClose: () => void;
};

export const OverviewFilePreview: React.FC<OverviewFilePreviewProps> = ({
  open,
  preview,
  sourceLabel,
  targetLabel,
  loading,
  error,
  onClose,
}) => {
  const sourceRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef<HTMLDivElement>(null);

  const sourceColumns = preview?.source_columns ?? [];
  const targetColumns = preview?.target_columns ?? [];
  const cappedSource = useMemo(() => capColumns(sourceColumns), [sourceColumns]);
  const cappedTarget = useMemo(() => capColumns(targetColumns), [targetColumns]);
  const rowCount = preview
    ? Math.max(
      preview.sample_row_count ?? 0,
      maxSampleRows(cappedSource.visible, preview.source_samples ?? {}),
      maxSampleRows(cappedTarget.visible, preview.target_samples ?? {}),
    )
    : 0;

  const sourceRows = useMemo(
    () => buildDataRows(cappedSource.visible, preview?.source_samples ?? {}, rowCount),
    [cappedSource.visible, preview?.source_samples, rowCount],
  );
  const targetRows = useMemo(
    () => buildDataRows(cappedTarget.visible, preview?.target_samples ?? {}, rowCount),
    [cappedTarget.visible, preview?.target_samples, rowCount],
  );

  const handleSourceScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (targetRef.current) {
      targetRef.current.scrollTop = e.currentTarget.scrollTop;
      targetRef.current.scrollLeft = e.currentTarget.scrollLeft;
    }
  };

  const handleTargetScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (sourceRef.current) {
      sourceRef.current.scrollTop = e.currentTarget.scrollTop;
      sourceRef.current.scrollLeft = e.currentTarget.scrollLeft;
    }
  };

  const renderTable = (
    side: 'source' | 'target',
    columns: string[],
    rows: string[][],
    scrollRef: React.RefObject<HTMLDivElement | null>,
    onScroll: (e: React.UIEvent<HTMLDivElement>) => void,
    headerIcon: React.ReactNode,
    headerLabel: string,
    headerTone: 'dark' | 'light',
  ) => (
    <div className={styles.panel}>
      <div className={`${styles.panelHeader} ${headerTone === 'dark' ? styles.panelHeaderDark : styles.panelHeaderLight}`}>
        {headerIcon}
        <span className={styles.panelHeaderLabel}>
          {headerLabel}
        </span>
      </div>
      <div ref={scrollRef} onScroll={onScroll} className={styles.scrollArea}>
        <table className={styles.table}>
          <thead className={styles.tableHead}>
            <tr>
              {loading && columns.length === 0
                ? Array.from({ length: 6 }, (_, i) => (
                  <th key={`skel-h-${side}-${i}`} className={styles.th}>
                    <SkeletonCell width={headerSkeletonWidths[i % 3]} />
                  </th>
                ))
                : columns.map((col) => (
                  <th key={`${side}-${col}`} className={`${styles.th} ${styles.thName}`}>
                    {col}
                  </th>
                ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 6 }, (_, rowIndex) => (
                <tr key={`skel-r-${side}-${rowIndex}`} className={styles.bodyRow}>
                  {Array.from({ length: Math.max(columns.length, 6) }, (_, colIndex) => (
                    <td key={colIndex} className={styles.td}>
                      <SkeletonCell width={cellSkeletonWidth(rowIndex, colIndex)} />
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={Math.max(columns.length, 1)} className={styles.emptyCell}>
                  No sample rows available.
                </td>
              </tr>
            ) : (
              rows.map((row, rowIndex) => (
                <tr key={`${side}-row-${rowIndex}`} className={styles.bodyRow}>
                  {row.map((cell, colIndex) => (
                    <td key={`${side}-cell-${rowIndex}-${colIndex}`} className={`${styles.td} ${styles.tdData}`}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width="min(1200px, 92vw)"
      centered
      destroyOnHidden={false}
      title="File preview"
      classNames={{ body: styles.modalBody }}
    >
      <p className={styles.description}>
        First ~4 KB of each file — column headers and sample rows. Scroll horizontally in either panel to keep both in sync.
      </p>

      {error && (
        <div className={styles.errorBanner}>
          {error}
        </div>
      )}

      {(cappedSource.hiddenCount > 0 || cappedTarget.hiddenCount > 0) && (
        <div className={styles.errorBanner}>
          Showing first {MAX_RENDER_COLUMNS} columns only
          {cappedSource.hiddenCount > 0 ? ` (source: +${cappedSource.hiddenCount} more)` : ''}
          {cappedTarget.hiddenCount > 0 ? ` (target: +${cappedTarget.hiddenCount} more)` : ''}.
        </div>
      )}

      <div className={styles.panelsRow}>
        {renderTable(
          'source',
          cappedSource.visible,
          sourceRows,
          sourceRef,
          handleSourceScroll,
          <FileTextOutlined />,
          `Source · ${sourceLabel}`,
          'dark',
        )}
        {renderTable(
          'target',
          cappedTarget.visible,
          targetRows,
          targetRef,
          handleTargetScroll,
          <DatabaseOutlined />,
          `Target · ${targetLabel}`,
          'light',
        )}
      </div>
    </Modal>
  );
};
