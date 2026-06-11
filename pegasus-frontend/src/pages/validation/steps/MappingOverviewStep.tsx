import React, { useEffect, useState } from 'react';
import {
  DatabaseOutlined, FileTextOutlined, ArrowRightOutlined,
  CheckCircleFilled, WarningFilled, ProfileOutlined,
  HddOutlined, TableOutlined, BarcodeOutlined
} from '@ant-design/icons';

import { Api, type FileDetectionResponse } from '../../../shared/api/Api';
import { useAppSelector } from '../../../redux/store';

const basename = (path: string) => path.split(/[/\\]/).pop() ?? path;

const formatBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

const columnCount = (detection: FileDetectionResponse | null) => {
  const meta = detection?.schema?.metadata;
  if (meta && typeof meta.column_count === 'number') return meta.column_count;
  return null;
};

export const MappingOverviewStep: React.FC = () => {
  const { sourcePath, targetPath } = useAppSelector((s) => s.validation.validationForm);
  const [sourceDetection, setSourceDetection] = useState<FileDetectionResponse | null>(null);
  const [targetDetection, setTargetDetection] = useState<FileDetectionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loading = Boolean(sourcePath && targetPath && !sourceDetection && !targetDetection && !error);

  useEffect(() => {
    if (!sourcePath || !targetPath) return;
    let cancelled = false;
    Promise.all([Api.detectLocalFile(sourcePath), Api.detectLocalFile(targetPath)])
      .then(([src, tgt]) => {
        if (!cancelled) {
          setSourceDetection(src.data);
          setTargetDetection(tgt.data);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError('Could not detect file metadata from server');
      });
    return () => { cancelled = true; };
  }, [sourcePath, targetPath]);

  const sourceStats = {
    name: sourcePath ? basename(sourcePath) : '—',
    path: sourcePath ?? '—',
    format: sourceDetection?.suggested_file_format ?? sourceDetection?.dataset_model ?? '—',
    sizeBytes: sourceDetection?.file_size_bytes ?? 0,
    columns: columnCount(sourceDetection),
  };

  const targetStats = {
    name: targetPath ? basename(targetPath) : '—',
    path: targetPath ?? '—',
    format: targetDetection?.suggested_file_format ?? targetDetection?.dataset_model ?? '—',
    sizeBytes: targetDetection?.file_size_bytes ?? 0,
    columns: columnCount(targetDetection),
  };

  const runComparison = () => {
    if (!sourceDetection || !targetDetection) {
      return { status: 'warning' as const, title: 'Awaiting detection', message: loading ? 'Loading file profiles…' : (error ?? 'Select files in step 1.'), mismatches: { size: false, columns: false, rows: false } };
    }
    const sizeDiff = sourceStats.sizeBytes > 0
      ? Math.abs(sourceStats.sizeBytes - targetStats.sizeBytes) / sourceStats.sizeBytes
      : 0;
    const colDiff = sourceStats.columns && targetStats.columns
      ? Math.abs(sourceStats.columns - targetStats.columns) / sourceStats.columns
      : 0;
    const mismatches = {
      size: sizeDiff > 0.2,
      columns: colDiff > 0.2,
      rows: false,
    };
    const issues: string[] = [];
    if (mismatches.size) issues.push('File Size');
    if (mismatches.columns) issues.push('Columns');
    if (issues.length > 0) {
      return {
        status: 'warning' as const,
        title: 'Significant Mismatch Detected',
        message: `Discrepancy in: ${issues.join(', ')}. Verify these are the correct files.`,
        mismatches,
      };
    }
    return {
      status: 'success' as const,
      title: 'Litmus Test Passed',
      message: 'Source and target profiles look compatible.',
      mismatches,
    };
  };

  const alert = runComparison();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '24px' }}>
        <div style={{ flex: 1, backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '12px', padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <FileTextOutlined style={{ color: '#1677ff' }} />
            <span style={{ fontSize: '12px', color: '#1677ff', fontWeight: 700, textTransform: 'uppercase' }}>Source</span>
          </div>
          <h4 style={{ fontSize: '18px', margin: '0 0 4px 0' }}>{sourceStats.name}</h4>
          <p style={{ fontSize: '12px', color: '#727786', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{sourceStats.path}</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
            <Row icon={<ProfileOutlined />} label="Format" value={sourceStats.format} warn={false} />
            <Row icon={<HddOutlined />} label="Size" value={formatBytes(sourceStats.sizeBytes)} warn={alert.mismatches.size} />
            <Row icon={<TableOutlined />} label="Columns" value={sourceStats.columns?.toString() ?? '—'} warn={alert.mismatches.columns} />
            <Row icon={<BarcodeOutlined />} label="Rows" value="—" warn={false} />
          </div>
        </div>

        <ArrowRightOutlined style={{ fontSize: '20px', color: '#727786' }} />

        <div style={{ flex: 1, backgroundColor: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '12px', padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <DatabaseOutlined style={{ color: '#16a34a' }} />
            <span style={{ fontSize: '12px', color: '#16a34a', fontWeight: 700, textTransform: 'uppercase' }}>Target</span>
          </div>
          <h4 style={{ fontSize: '18px', margin: '0 0 4px 0' }}>{targetStats.name}</h4>
          <p style={{ fontSize: '12px', color: '#727786', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{targetStats.path}</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
            <Row icon={<ProfileOutlined />} label="Format" value={targetStats.format} warn={false} />
            <Row icon={<HddOutlined />} label="Size" value={formatBytes(targetStats.sizeBytes)} warn={alert.mismatches.size} />
            <Row icon={<TableOutlined />} label="Columns" value={targetStats.columns?.toString() ?? '—'} warn={alert.mismatches.columns} />
            <Row icon={<BarcodeOutlined />} label="Rows" value="—" warn={false} />
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px 20px', borderRadius: '8px', backgroundColor: alert.status === 'success' ? '#f0fdf4' : '#fffbeb', border: alert.status === 'success' ? '1px solid #bbf7d0' : '1px solid #fde68a' }}>
        {alert.status === 'success' ? (
          <CheckCircleFilled style={{ color: '#16a34a', fontSize: '20px' }} />
        ) : (
          <WarningFilled style={{ color: '#d97706', fontSize: '20px' }} />
        )}
        <div>
          <h5 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: 700 }}>{alert.title}</h5>
          <p style={{ margin: 0, fontSize: '13px' }}>{alert.message}</p>
        </div>
      </div>
    </div>
  );
};

const Row: React.FC<{ icon: React.ReactNode; label: string; value: string; warn: boolean }> = ({ icon, label, value, warn }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f0eded', paddingBottom: '8px' }}>
    <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}>{icon} {label}</span>
    <span style={{ fontSize: '13px', fontWeight: 600, color: warn ? '#ba1a1a' : '#1b1b1c' }}>{value}</span>
  </div>
);
