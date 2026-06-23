import React, { useMemo, useRef } from 'react';
import { Modal } from 'antd';
import { DatabaseOutlined, FileTextOutlined } from '@ant-design/icons';
import type { LocalColumnPreviewResponse } from '../../../shared/api/Api';

const SkeletonCell: React.FC<{ width?: string }> = ({ width = '100%' }) => (
  <div
    style={{
      width,
      height: '14px',
      backgroundColor: '#e2e8f0',
      borderRadius: '4px',
      animation: 'overview-preview-skeleton 1.5s ease-in-out infinite',
    }}
  />
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
  const rowCount = preview
    ? Math.max(
      preview.sample_row_count ?? 0,
      maxSampleRows(sourceColumns, preview.source_samples ?? {}),
      maxSampleRows(targetColumns, preview.target_samples ?? {}),
    )
    : 0;

  const sourceRows = useMemo(
    () => buildDataRows(sourceColumns, preview?.source_samples ?? {}, rowCount),
    [sourceColumns, preview?.source_samples, rowCount],
  );
  const targetRows = useMemo(
    () => buildDataRows(targetColumns, preview?.target_samples ?? {}, rowCount),
    [targetColumns, preview?.target_samples, rowCount],
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
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#fff',
        borderRadius: '12px',
        border: '1px solid #d9d9d9',
        overflow: 'hidden',
        minWidth: 0,
      }}
    >
      <div
        style={{
          backgroundColor: headerTone === 'dark' ? '#234B5F' : '#f0eded',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          color: headerTone === 'dark' ? '#fff' : '#1b1b1c',
        }}
      >
        {headerIcon}
        <span style={{ fontSize: '13px', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {headerLabel}
        </span>
      </div>
      <div ref={scrollRef} onScroll={onScroll} style={{ overflow: 'auto', maxHeight: 'min(52vh, 480px)' }}>
        <table style={{ borderCollapse: 'collapse', textAlign: 'left', whiteSpace: 'nowrap' }}>
          <thead style={{ position: 'sticky', top: 0, backgroundColor: '#f8fafc', zIndex: 1 }}>
            <tr>
              {loading && columns.length === 0
                ? Array.from({ length: 6 }, (_, i) => (
                  <th
                    key={`skel-h-${side}-${i}`}
                    style={{ padding: '10px 14px', borderBottom: '1px solid #e2e8f0', fontSize: '12px', color: '#414755' }}
                  >
                    <SkeletonCell width={`${40 + (i % 3) * 15}%`} />
                  </th>
                ))
                : columns.map((col) => (
                  <th
                    key={`${side}-${col}`}
                    style={{
                      padding: '10px 14px',
                      borderBottom: '1px solid #e2e8f0',
                      fontSize: '12px',
                      color: '#414755',
                      fontWeight: 700,
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {col}
                  </th>
                ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 6 }, (_, rowIndex) => (
                <tr key={`skel-r-${side}-${rowIndex}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  {Array.from({ length: Math.max(columns.length, 6) }, (_, colIndex) => (
                    <td key={colIndex} style={{ padding: '10px 14px' }}>
                      <SkeletonCell width={`${45 + ((rowIndex + colIndex) % 4) * 10}%`} />
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={Math.max(columns.length, 1)} style={{ padding: '24px', textAlign: 'center', color: '#727786', fontSize: '13px' }}>
                  No sample rows available.
                </td>
              </tr>
            ) : (
              rows.map((row, rowIndex) => (
                <tr key={`${side}-row-${rowIndex}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  {row.map((cell, colIndex) => (
                    <td
                      key={`${side}-cell-${rowIndex}-${colIndex}`}
                      style={{
                        padding: '10px 14px',
                        fontSize: '12px',
                        fontFamily: 'var(--font-mono)',
                        color: '#1b1b1c',
                      }}
                    >
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
      styles={{ body: { paddingTop: 8 } }}
    >
      <style>{`@keyframes overview-preview-skeleton { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }`}</style>

      <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: '#727786' }}>
        First ~4 KB of each file — column headers and sample rows. Scroll horizontally in either panel to keep both in sync.
      </p>

      {error && (
        <div style={{ padding: '12px', marginBottom: '16px', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: '8px', fontSize: '13px' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: '16px', alignItems: 'stretch' }}>
        {renderTable(
          'source',
          sourceColumns,
          sourceRows,
          sourceRef,
          handleSourceScroll,
          <FileTextOutlined />,
          `Source · ${sourceLabel}`,
          'dark',
        )}
        {renderTable(
          'target',
          targetColumns,
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
