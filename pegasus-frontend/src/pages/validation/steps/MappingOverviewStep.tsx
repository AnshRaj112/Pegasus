import React, { useEffect, useState } from 'react';
import {
  DatabaseOutlined, FileTextOutlined, ArrowRightOutlined,
  CheckCircleFilled, WarningFilled, ProfileOutlined,
  HddOutlined, TableOutlined, BarcodeOutlined, BuildOutlined
} from '@ant-design/icons';
import { Api, type CloudFileProfileResponse, type GoogleCloudStorageConfig } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { EyeOutlined } from '@ant-design/icons';

const formatBytes = (bytes: number | null) => {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

const getFriendlyFormatLabel = (format: string | null | undefined): string => {
  if (!format || format === '—' || format === '…') return format ?? '—';
  const fmt = format.toLowerCase().trim();
  if (fmt === 'empty file') return 'Empty File';
  if (['csv', 'tsv', 'psv', 'tsc'].includes(fmt) || fmt.includes('delimited')) return 'Delimited File';
  if (['fixed-width', 'fixed_width', 'fixed', 'fixedwidth'].includes(fmt)) return 'Fixed Width';
  if (['archive', '7z', 'rar', 'container', 'decompress_first', 'gzip', 'bzip2', 'xz', 'zstd', 'lz4'].includes(fmt)) return 'Archive';
  return fmt.charAt(0).toUpperCase() + fmt.slice(1);
};

const formatCount = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString();
const gsPath = (bucket: string | null, objectName: string | null) => bucket && objectName ? `gs://${bucket}/${objectName}` : '—';
const cloudObjectKey = (cloud: GoogleCloudStorageConfig | null): string => cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '';

// ⚡ Safely stringify booleans for the UI
const formatBoolean = (val: boolean | null | undefined) => {
  if (val === true) return 'Yes';
  if (val === false) return 'No';
  return '—';
};

type FileProfileState = { profile: CloudFileProfileResponse | null; loading: boolean; error: boolean; };
const emptyProfileState: FileProfileState = { profile: null, loading: false, error: false };

const SkeletonBlock: React.FC<{ width?: string; height?: string }> = ({ width = '100%', height = '16px' }) => (
  <div style={{ width, height, backgroundColor: '#e2e8f0', borderRadius: '4px', animation: 'skeleton-pulse 1.5s ease-in-out infinite' }} />
);

const FileCard: React.FC<{ label: string; color: string; stats: any; warn: any; loading: boolean; icon?: React.ReactNode; }> = ({ label, color, stats, warn, loading, icon }) => (
  <div style={{ flex: 1, backgroundColor: '#fff', border: '1px solid #d9d9d9', borderRadius: '12px', padding: '24px', minWidth: '300px' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color }}>
      {icon ?? <FileTextOutlined />}
      <span style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase' }}>{label}</span>
    </div>

    <h4 style={{ margin: '0 0 4px 0', fontSize: '18px', minHeight: '24px' }}>
      {loading ? <SkeletonBlock width="60%" height="24px" /> : stats.name}
    </h4>
    <div style={{ fontSize: '12px', color: '#727786', fontFamily: 'var(--font-mono)', wordBreak: 'break-all', minHeight: '16px' }}>
      {loading ? <SkeletonBlock width="90%" height="16px" /> : stats.path}
    </div>

    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
      <Row icon={<ProfileOutlined />} label="Format" value={stats.format} loading={loading} />
      <Row icon={<HddOutlined />} label="Size" value={formatBytes(stats.sizeBytes)} warn={warn.size} loading={loading} />
      <Row icon={<TableOutlined />} label="Columns" value={formatCount(stats.columnCount)} warn={warn.columns} loading={loading} />
      <Row icon={<BarcodeOutlined />} label="Rows" value={formatCount(stats.rowCount)} warn={warn.rows} loading={loading} />
      {/* ⚡ Added new Header & Footer attributes */}
      <Row icon={<BuildOutlined />} label="Header" value={stats.header} loading={loading} />
      <Row icon={<BuildOutlined />} label="Footer" value={stats.footer} loading={loading} />
      <Row icon={<EyeOutlined />} label="Preview" value={stats.preview} loading={loading} />
    </div>
  </div>
);

const Row: React.FC<{ icon: React.ReactNode; label: string; value: string; warn?: boolean; loading: boolean }> = ({ icon, label, value, warn, loading }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f0eded', paddingBottom: '8px', alignItems: 'center' }}>
    <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}>{icon} {label}</span>
    <span style={{ fontSize: '13px', fontWeight: 600, color: warn ? '#ba1a1a' : '#1b1b1c' }}>
      {loading ? <SkeletonBlock width="48px" height="16px" /> : value}
    </span>
  </div>
);

export const MappingOverviewStep: React.FC = () => {
  const [isHovered, setIsHovered] = useState(false);
  const [isActive, setIsActive] = useState(false);
  const dispatch = useAppDispatch();
  const form = useAppSelector((s) => s.validation.validationForm);
  const cache = useAppSelector((s) => s.validation.overviewProfileCache);

  const sourceKey = cloudObjectKey(form.sourceCloud);
  const targetKey = cloudObjectKey(form.targetCloud);
  const cacheHit = cache?.sourceKey === sourceKey && cache?.targetKey === targetKey;

  const sourceProfile: FileProfileState = !form.sourceCloud ? emptyProfileState : cacheHit ? { profile: cache.source, loading: false, error: cache.sourceError } : { profile: null, loading: true, error: false };
  const targetProfile: FileProfileState = !form.targetCloud ? emptyProfileState : cacheHit ? { profile: cache.target, loading: false, error: cache.targetError } : { profile: null, loading: true, error: false };

  useEffect(() => {
    if (!form.sourceCloud || !form.targetCloud || !sourceKey || !targetKey || cacheHit) return;

    let cancelled = false;
    const nextCache = { sourceKey, targetKey, source: null as CloudFileProfileResponse | null, target: null as CloudFileProfileResponse | null, sourceError: false, targetError: false };
    const commit = () => { if (!cancelled) dispatch(validationActions.setOverviewProfileCache({ ...nextCache })); };

    Promise.all([
      Api.profileCloudFile({ cloud: form.sourceCloud, delimiter: form.delimiter || 'auto', has_header: form.hasHeader }),
      Api.profileCloudFile({ cloud: form.targetCloud, delimiter: form.delimiter || 'auto', has_header: form.hasHeader }),
    ])
      .then(([sourceRes, targetRes]) => { nextCache.source = sourceRes.data; nextCache.target = targetRes.data; commit(); })
      .catch(() => { nextCache.sourceError = true; nextCache.targetError = true; commit(); });

    return () => { cancelled = true; };
  }, [form.sourceCloud, form.targetCloud, sourceKey, targetKey, cacheHit, dispatch, form.delimiter, form.hasHeader]);

  const buttonStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    backgroundColor: isHovered ? '#1a3847' : '#234B5F', // Darkens slightly on hover
    color: '#ffffff',
    border: isHovered ? '1.5px solid #1a3847' : '1.5px solid #234B5F',
    padding: '8px 10px',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 0.2s ease-in-out',
    transform: isActive ? 'scale(0.98)' : 'scale(1)', // Slight press effect on click
    boxShadow: isHovered ? '0 4px 6px -1px rgba(35, 75, 95, 0.2)' : 'none',
  };

  const sourceStats = {
    name: form.sourceFileName ?? '—',
    path: gsPath(form.sourceCloud?.bucket ?? null, form.sourceCloud?.object_name ?? null),
    format: getFriendlyFormatLabel(form.sourceFileSize === 0 ? 'empty file' : sourceProfile.profile?.file_format),
    sizeBytes: sourceProfile.profile?.file_size_bytes ?? form.sourceFileSize,
    columnCount: form.sourceFileSize === 0 ? 0 : sourceProfile.profile?.column_count ?? null,
    rowCount: form.sourceFileSize === 0 ? 0 : sourceProfile.profile?.row_count ?? null,
    // ⚡ Header and footer mapping
    header: formatBoolean(sourceProfile.profile?.has_header),
    footer: formatBoolean((sourceProfile.profile as any)?.has_footer), // Assuming API might pass this later
    preview: <button
      style={buttonStyle}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setIsActive(false); // Resets the click effect if the user drags the mouse away
      }}
      onMouseDown={() => setIsActive(true)}
      onMouseUp={() => setIsActive(false)}
    >
      <EyeOutlined style={{ fontSize: '16px' }} />
    </button>,
  };

  const targetStats = {
    name: form.targetFileName ?? '—',
    path: gsPath(form.targetCloud?.bucket ?? null, form.targetCloud?.object_name ?? null),
    format: getFriendlyFormatLabel(targetProfile.profile?.file_format),
    sizeBytes: targetProfile.profile?.file_size_bytes ?? form.targetFileSize,
    columnCount: targetProfile.profile?.column_count ?? null,
    rowCount: targetProfile.profile?.row_count ?? null,
    // ⚡ Header and footer mapping
    header: formatBoolean(targetProfile.profile?.has_header),
    footer: formatBoolean((targetProfile.profile as any)?.has_footer),
    preview: <button
      style={buttonStyle}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setIsActive(false); // Resets the click effect if the user drags the mouse away
      }}
      onMouseDown={() => setIsActive(true)}
      onMouseUp={() => setIsActive(false)}
    >
      <EyeOutlined style={{ fontSize: '16px' }} />
    </button>,
  };

  

  const isFetching = sourceProfile.loading || targetProfile.loading;

  // ⚡ Updated to aggregate ALL warnings simultaneously
  const runComparison = () => {
    if (!form.sourceCloud || !form.targetCloud) return { status: 'warning' as const, title: 'Files not selected', message: 'Select source and target GCS objects in step 1.', mismatches: { size: false, columns: false, rows: false } };
    if (isFetching) return { status: 'warning' as const, title: 'Analyzing files', message: 'Detecting format and estimating file shape…', mismatches: { size: false, columns: false, rows: false } };

    const sizeDiff = sourceStats.sizeBytes && targetStats.sizeBytes ? Math.abs(sourceStats.sizeBytes - targetStats.sizeBytes) / sourceStats.sizeBytes : 0;
    const columnMismatch = sourceStats.columnCount != null && targetStats.columnCount != null && sourceStats.columnCount !== targetStats.columnCount;
    const rowDiff = sourceStats.rowCount != null && targetStats.rowCount != null ? Math.abs(sourceStats.rowCount - targetStats.rowCount) / Math.max(sourceStats.rowCount, targetStats.rowCount) : 0;

    const rowMismatch = rowDiff > 0.05;
    const mismatches = { size: sizeDiff > 0.2, columns: columnMismatch, rows: rowMismatch };

    const issues = [];
    if (mismatches.columns) issues.push(`Columns (${sourceStats.columnCount?.toLocaleString()} vs ${targetStats.columnCount?.toLocaleString()})`);
    if (mismatches.rows) issues.push(`Rows (${sourceStats.rowCount?.toLocaleString()} vs ${targetStats.rowCount?.toLocaleString()})`);
    if (mismatches.size) issues.push(`Size (>20% diff)`);

    if (issues.length > 0) {
      return {
        status: 'warning' as const,
        title: issues.length > 1 ? 'Multiple Mismatches Detected' : 'Mismatch Detected',
        message: `Source and target differ in: ${issues.join(' | ')}.`,
        mismatches
      };
    }

    return { status: 'success' as const, title: 'Ready for mapping', message: 'GCS source and target objects are selected.', mismatches };
  };

  const alert = runComparison();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <style>{`@keyframes skeleton-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }`}</style>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '24px' }}>
        <FileCard label="Source" color="#234B5F" stats={sourceStats} warn={alert.mismatches} loading={isFetching} />
        <ArrowRightOutlined style={{ fontSize: '20px', color: '#727786' }} />
        <FileCard label="Target" color="#234B5F" icon={<DatabaseOutlined />} stats={targetStats} warn={alert.mismatches} loading={isFetching} />
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px 20px', borderRadius: '8px', backgroundColor: alert.status === 'success' ? '#f0fdf4' : '#fffbeb', border: `1px solid ${alert.status === 'success' ? '#bbf7d0' : '#fde68a'}` }}>
        {alert.status === 'success' ? <CheckCircleFilled style={{ color: '#16a34a', fontSize: '20px' }} /> : <WarningFilled style={{ color: '#d97706', fontSize: '20px' }} />}
        <div>
          <h5 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: 700 }}>{alert.title}</h5>
          <p style={{ margin: 0, fontSize: '13px' }}>{alert.message}</p>
        </div>
      </div>
    </div>
  );
};