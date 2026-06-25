import React, { useCallback, useEffect, useState } from 'react';
import {
  DatabaseOutlined, FileTextOutlined, ArrowRightOutlined,
  CheckCircleFilled, WarningFilled, CloseCircleFilled, ProfileOutlined,
  HddOutlined, TableOutlined, BarcodeOutlined, BuildOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { Api, CloudFileProfileResponse, FixedWidthColumnPreview, GoogleCloudStorageConfig, LocalColumnPreviewResponse } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { validationActions } from '../Validation.reducer';
import { OverviewFilePreview } from './OverviewFilePreview';
import { OverviewJsonPreview } from './OverviewJsonPreview';
import { assessEmptyValidationFiles, isValidationFileEmpty } from '../validationEmptyFiles';
import { isFixedWidthFormat } from '../fixedWidthFormat';
import { isJsonFileName, profileLooksJson } from '../jsonFormat';
import { FixedWidthLayoutPanel } from './FixedWidthLayoutPanel';
import { formatDetectionLabel } from '../../../shared/formatDisplayLabel';

const formatBytes = (bytes: number | null) => {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

const formatCount = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString();
const gsPath = (bucket: string | null, objectName: string | null) => bucket && objectName ? `gs://${bucket}/${objectName}` : '—';
const cloudObjectKey = (cloud: GoogleCloudStorageConfig | null): string => cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '';

const formatBoolean = (val: boolean | null | undefined) => {
  if (val === true) return 'Yes';
  if (val === false) return 'No';
  return '—';
};

const resolveCloudFormatLabel = (
  profile: CloudFileProfileResponse | null,
  fileName: string | null,
  empty: boolean,
): string => {
  if (empty) return formatDetectionLabel('empty');
  const raw = profile?.suggested_file_format ?? profile?.file_format;
  if (raw) return formatDetectionLabel(raw);
  if (isJsonFileName(fileName)) return formatDetectionLabel('json');
  return '—';
};

type FileProfileState = { profile: CloudFileProfileResponse | null; loading: boolean; error: boolean; };
const emptyProfileState: FileProfileState = { profile: null, loading: false, error: false };

const SkeletonBlock: React.FC<{ width?: string; height?: string }> = ({ width = '100%', height = '16px' }) => (
  <div style={{ width, height, backgroundColor: '#e2e8f0', borderRadius: '4px', animation: 'skeleton-pulse 1.5s ease-in-out infinite' }} />
);

const PreviewButton: React.FC<{ onClick: () => void; disabled?: boolean }> = ({ onClick, disabled }) => {
  const [isHovered, setIsHovered] = useState(false);
  const [isActive, setIsActive] = useState(false);

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setIsActive(false);
      }}
      onMouseDown={() => setIsActive(true)}
      onMouseUp={() => setIsActive(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        backgroundColor: disabled ? '#e5e2e1' : isHovered ? '#1a3847' : '#234B5F',
        color: disabled ? '#727786' : '#ffffff',
        border: disabled ? '1.5px solid #e5e2e1' : isHovered ? '1.5px solid #1a3847' : '1.5px solid #234B5F',
        padding: '8px 10px',
        borderRadius: '6px',
        fontSize: '12px',
        fontWeight: 500,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.2s ease-in-out',
        transform: isActive ? 'scale(0.98)' : 'scale(1)',
        boxShadow: isHovered && !disabled ? '0 4px 6px -1px rgba(35, 75, 95, 0.2)' : 'none',
      }}
    >
      <EyeOutlined style={{ fontSize: '16px' }} />
    </button>
  );
};

const FileCard: React.FC<{
  label: string;
  color: string;
  stats: {
    name: string;
    path: string;
    format: string;
    sizeBytes: number | null;
    columnCount: number | null;
    rowCount: number | null;
    header: string;
    footer: string;
    preview: React.ReactNode;
  };
  warn: { size: boolean; columns: boolean; rows: boolean };
  loading: boolean;
  icon?: React.ReactNode;
  isEmpty?: boolean;
}> = ({ label, color, stats, warn, loading, icon, isEmpty }) => (
  <div style={{
    flex: 1,
    backgroundColor: '#fff',
    border: `1px solid ${isEmpty ? '#fecaca' : '#d9d9d9'}`,
    borderRadius: '12px',
    padding: '24px',
    minWidth: '300px',
    boxShadow: isEmpty ? 'inset 0 0 0 1px #fee2e2' : undefined,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color }}>
      {icon ?? <FileTextOutlined />}
      <span style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase' }}>{label}</span>
    </div>

    <h4 style={{ margin: '0 0 4px 0', fontSize: '18px', minHeight: '24px', color: isEmpty ? '#ba1a1a' : undefined }}>
      {loading ? <SkeletonBlock width="60%" height="24px" /> : stats.name}
    </h4>
    <div style={{ fontSize: '12px', color: '#727786', fontFamily: 'var(--font-mono)', wordBreak: 'break-all', minHeight: '16px' }}>
      {loading ? <SkeletonBlock width="90%" height="16px" /> : stats.path}
    </div>

    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
      <Row icon={<ProfileOutlined />} label="Format" value={isEmpty ? 'Empty' : stats.format} loading={loading} warn={isEmpty} />
      <Row icon={<HddOutlined />} label="Size" value={formatBytes(stats.sizeBytes)} warn={warn.size || isEmpty} loading={loading} />
      <Row icon={<TableOutlined />} label="Columns" value={formatCount(stats.columnCount)} warn={warn.columns} loading={loading} />
      <Row icon={<BarcodeOutlined />} label="Rows" value={isEmpty ? '0 (empty)' : formatCount(stats.rowCount)} warn={warn.rows || isEmpty} loading={loading} />
      <Row icon={<BuildOutlined />} label="Header" value={stats.header} loading={loading} />
      <Row icon={<BuildOutlined />} label="Footer" value={stats.footer} loading={loading} />
      <Row icon={<EyeOutlined />} label="Preview" value={stats.preview} loading={loading} isNode />
    </div>
  </div>
);

const Row: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  warn?: boolean;
  loading: boolean;
  isNode?: boolean;
}> = ({ icon, label, value, warn, loading, isNode }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f0eded', paddingBottom: '8px', alignItems: 'center' }}>
    <span style={{ fontSize: '13px', color: '#414755', display: 'flex', alignItems: 'center', gap: '6px' }}>{icon} {label}</span>
    <span style={{ fontSize: '13px', fontWeight: 600, color: warn ? '#ba1a1a' : '#1b1b1c' }}>
      {loading && !isNode ? <SkeletonBlock width="48px" height="16px" /> : value}
    </span>
  </div>
);

export const MappingOverviewStep: React.FC = () => {
  const dispatch = useAppDispatch();
  const form = useAppSelector((s) => s.validation.validationForm);
  const cache = useAppSelector((s) => s.validation.overviewProfileCache);

  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<LocalColumnPreviewResponse | null>(null);
  const [fixedWidthLoading, setFixedWidthLoading] = useState(false);
  const [fixedWidthError, setFixedWidthError] = useState<string | null>(null);

  const sourceKey = cloudObjectKey(form.sourceCloud);
  const targetKey = cloudObjectKey(form.targetCloud);
  const previewPairKey = `${sourceKey}|${targetKey}|${form.delimiter || 'auto'}|${form.hasHeader}`;
  const cacheHit = cache?.sourceKey === sourceKey && cache?.targetKey === targetKey
    && !cache.sourceError && !cache.targetError;

  const sourceProfile: FileProfileState = !form.sourceCloud ? emptyProfileState : cacheHit ? { profile: cache.source, loading: false, error: cache.sourceError } : { profile: null, loading: true, error: false };
  const targetProfile: FileProfileState = !form.targetCloud ? emptyProfileState : cacheHit ? { profile: cache.target, loading: false, error: cache.targetError } : { profile: null, loading: true, error: false };
  const isFetching = sourceProfile.loading || targetProfile.loading;
  const sourceEmpty = isValidationFileEmpty(
    form.sourceFileSize,
    sourceProfile.profile,
    sourceProfile.error,
  );
  const targetEmpty = isValidationFileEmpty(
    form.targetFileSize,
    targetProfile.profile,
    targetProfile.error,
  );
  const isFixedWidth = !sourceEmpty && !targetEmpty && (
    isFixedWidthFormat(sourceProfile.profile?.suggested_file_format ?? sourceProfile.profile?.file_format)
    || isFixedWidthFormat(targetProfile.profile?.suggested_file_format ?? targetProfile.profile?.file_format)
  );
  const sourceLooksJson = profileLooksJson(sourceProfile.profile, form.sourceFileName);
  const targetLooksJson = profileLooksJson(targetProfile.profile, form.targetFileName);
  const isJson = !sourceEmpty && !targetEmpty && !isFixedWidth && sourceLooksJson && targetLooksJson;

  useEffect(() => {
    if (!isJson || isFetching) return;
    dispatch(validationActions.setValidationForm({
      detectedFileFormat: 'json',
      uidColumn: form.uidColumn || 'document',
      columnMappings: [],
    }));
  }, [isJson, isFetching, dispatch, form.uidColumn]);

  useEffect(() => {
    if (!isFixedWidth || isFetching) return;
    dispatch(validationActions.setValidationForm({ detectedFileFormat: 'fixed-width' }));
  }, [isFixedWidth, isFetching, dispatch]);

  useEffect(() => {
    if (!form.sourceCloud || !form.targetCloud || !isFixedWidth || form.fixedWidthColumns.length > 0) {
      if (!isFixedWidth) {
        setFixedWidthLoading(false);
        setFixedWidthError(null);
      }
      return;
    }

    let cancelled = false;
    setFixedWidthLoading(true);
    setFixedWidthError(null);

    Api.previewFixedWidthLayout({
      source_cloud: form.sourceCloud,
      target_cloud: form.targetCloud,
      uid_column: form.uidColumn,
      delimiter: form.delimiter || 'auto',
      has_header: form.hasHeader,
    })
      .then((res) => {
        if (cancelled) return;
        const { columns, suggested_join_column: joinCol, line_width: lineWidth } = res.data;
        dispatch(validationActions.setValidationForm({
          fixedWidthColumns: columns,
          fixedWidthLineWidth: lineWidth,
          uidColumn: form.uidColumn || joinCol,
          detectedFileFormat: 'fixed-width',
        }));
      })
      .catch((err: { response?: { data?: { detail?: unknown } } }) => {
        if (cancelled) return;
        const detail = err.response?.data?.detail;
        setFixedWidthError(typeof detail === 'string' ? detail : 'Could not infer fixed-width layout');
      })
      .finally(() => {
        if (!cancelled) setFixedWidthLoading(false);
      });

    return () => { cancelled = true; };
  }, [
    form.sourceCloud,
    form.targetCloud,
    form.uidColumn,
    form.delimiter,
    form.hasHeader,
    form.fixedWidthColumns.length,
    isFixedWidth,
    dispatch,
  ]);

  const handleFixedWidthChange = (columns: FixedWidthColumnPreview[]) => {
    dispatch(validationActions.setValidationForm({ fixedWidthColumns: columns }));
  };

  const handleJoinColumnChange = (joinColumn: string) => {
    dispatch(validationActions.setValidationForm({ uidColumn: joinColumn }));
  };

  useEffect(() => {
    if (!form.sourceCloud || !form.targetCloud || !sourceKey || !targetKey || cacheHit) return;

    let cancelled = false;
    const nextCache = { sourceKey, targetKey, source: null as CloudFileProfileResponse | null, target: null as CloudFileProfileResponse | null, sourceError: false, targetError: false };
    const commit = () => { if (!cancelled) dispatch(validationActions.setOverviewProfileCache({ ...nextCache })); };

    Promise.allSettled([
      Api.profileCloudFile({ cloud: form.sourceCloud, delimiter: form.delimiter || 'auto', has_header: form.hasHeader }),
      Api.profileCloudFile({ cloud: form.targetCloud, delimiter: form.delimiter || 'auto', has_header: form.hasHeader }),
    ])
      .then(([sourceResult, targetResult]) => {
        if (sourceResult.status === 'fulfilled') nextCache.source = sourceResult.value.data;
        else nextCache.sourceError = true;
        if (targetResult.status === 'fulfilled') nextCache.target = targetResult.value.data;
        else nextCache.targetError = true;
        commit();
      });

    return () => { cancelled = true; };
  }, [form.sourceCloud, form.targetCloud, sourceKey, targetKey, cacheHit, dispatch, form.delimiter, form.hasHeader]);

  useEffect(() => {
    if (!form.sourceCloud || !form.targetCloud || !sourceKey || !targetKey || isFixedWidth || isJson || isFetching) {
      setPreviewData(null);
      setPreviewError(null);
      setPreviewLoading(false);
      return;
    }

    let cancelled = false;
    setPreviewLoading(true);
    setPreviewError(null);

    Api.previewValidationColumns({
      source_cloud: form.sourceCloud,
      target_cloud: form.targetCloud,
      uid_column: form.uidColumn || 'id',
      delimiter: form.delimiter || 'auto',
      has_header: form.hasHeader,
    })
      .then((res) => {
        if (cancelled) return;
        setPreviewData(res.data);
      })
      .catch((err: { response?: { data?: { detail?: unknown } } }) => {
        if (cancelled) return;
        const detail = err.response?.data?.detail;
        const message = typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((item) => (typeof item === 'object' && item && 'msg' in item ? String((item as { msg: string }).msg) : String(item))).join('; ')
            : null;
        setPreviewError(message ?? 'Could not load file preview from server');
        setPreviewData(null);
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });

    return () => { cancelled = true; };
  }, [form.sourceCloud, form.targetCloud, form.uidColumn, form.delimiter, form.hasHeader, previewPairKey, sourceKey, targetKey, isFixedWidth, isJson, isFetching]);

  useEffect(() => {
    setPreviewOpen(false);
  }, [previewPairKey]);

  const openPreview = useCallback(() => {
    setPreviewOpen(true);
  }, []);

  const jsonPreviewReady = Boolean(
    sourceProfile.profile?.json_preview && targetProfile.profile?.json_preview,
  );

  const previewControl = isJson
    ? (jsonPreviewReady
      ? <PreviewButton onClick={openPreview} />
      : isFetching
        ? <SkeletonBlock width="36px" height="32px" />
        : '—')
    : previewData
      ? <PreviewButton onClick={openPreview} />
      : previewLoading
        ? <SkeletonBlock width="36px" height="32px" />
        : '—';

  const inferredColumnCount = isFixedWidth
    ? (form.fixedWidthColumns.length || sourceProfile.profile?.column_count || null)
    : isJson
      ? (sourceProfile.profile?.column_count ?? 1)
      : (sourceProfile.profile?.column_count ?? null);

  const inferredRowCount = (profile: CloudFileProfileResponse | null, empty: boolean) => {
    if (empty) return 0;
    if (isJson) return profile?.row_count ?? 1;
    return profile?.row_count ?? null;
  };

  const headerFooterLabel = (profile: CloudFileProfileResponse | null) =>
    isJson ? 'N/A' : formatBoolean(profile?.has_header);

  const sourceStats = {
    name: form.sourceFileName ?? '—',
    path: gsPath(form.sourceCloud?.bucket ?? null, form.sourceCloud?.object_name ?? null),
    format: resolveCloudFormatLabel(sourceProfile.profile, form.sourceFileName, sourceEmpty),
    sizeBytes: sourceProfile.profile?.file_size_bytes ?? form.sourceFileSize,
    columnCount: sourceEmpty ? 0 : inferredColumnCount,
    rowCount: inferredRowCount(sourceProfile.profile, sourceEmpty),
    header: headerFooterLabel(sourceProfile.profile),
    footer: isJson ? 'N/A' : formatBoolean((sourceProfile.profile as { has_footer?: boolean })?.has_footer),
    preview: previewControl,
  };

  const targetStats = {
    name: form.targetFileName ?? '—',
    path: gsPath(form.targetCloud?.bucket ?? null, form.targetCloud?.object_name ?? null),
    format: resolveCloudFormatLabel(targetProfile.profile, form.targetFileName, targetEmpty),
    sizeBytes: targetProfile.profile?.file_size_bytes ?? form.targetFileSize,
    columnCount: targetEmpty ? 0 : (isFixedWidth ? inferredColumnCount : isJson ? (targetProfile.profile?.column_count ?? 1) : targetProfile.profile?.column_count ?? null),
    rowCount: inferredRowCount(targetProfile.profile, targetEmpty),
    header: headerFooterLabel(targetProfile.profile),
    footer: isJson ? 'N/A' : formatBoolean((targetProfile.profile as { has_footer?: boolean })?.has_footer),
    preview: previewControl,
  };

  const emptyAssessment = assessEmptyValidationFiles({
    sourceSizeBytes: form.sourceFileSize,
    targetSizeBytes: form.targetFileSize,
    sourceProfile: sourceProfile.profile,
    targetProfile: targetProfile.profile,
    profilesLoading: isFetching,
    sourceProfileError: sourceProfile.error,
    targetProfileError: targetProfile.error,
  });

  const runComparison = () => {
    if (!form.sourceCloud || !form.targetCloud) {
      return {
        status: 'warning' as const,
        title: 'Files not selected',
        message: 'Select source and target GCS objects in step 1.',
        mismatches: { size: false, columns: false, rows: false },
        blocksMapping: true,
      };
    }
    if (isFetching) {
      return {
        status: 'warning' as const,
        title: 'Analyzing files',
        message: 'Detecting format and estimating file shape…',
        mismatches: { size: false, columns: false, rows: false },
        blocksMapping: false,
      };
    }
    if (emptyAssessment?.blocksMapping) {
      return {
        status: 'error' as const,
        title: emptyAssessment.title,
        message: emptyAssessment.message,
        mismatches: { size: false, columns: false, rows: false },
        blocksMapping: true,
      };
    }

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
        mismatches,
        blocksMapping: false,
      };
    }

    return {
      status: 'success' as const,
      title: 'Ready for mapping',
      message: 'GCS source and target objects are selected.',
      mismatches,
      blocksMapping: false,
    };
  };

  const alert = runComparison();
  const alertStyles = alert.status === 'success'
    ? { backgroundColor: '#f0fdf4', borderColor: '#bbf7d0', icon: <CheckCircleFilled style={{ color: '#16a34a', fontSize: '20px' }} /> }
    : alert.status === 'error'
      ? { backgroundColor: '#fef2f2', borderColor: '#fecaca', icon: <CloseCircleFilled style={{ color: '#dc2626', fontSize: '20px' }} /> }
      : { backgroundColor: '#fffbeb', borderColor: '#fde68a', icon: <WarningFilled style={{ color: '#d97706', fontSize: '20px' }} /> };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <style>{`@keyframes skeleton-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }`}</style>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '24px' }}>
        <FileCard label="Source" color="#234B5F" stats={sourceStats} warn={alert.mismatches} loading={isFetching} isEmpty={sourceEmpty} />
        <ArrowRightOutlined style={{ fontSize: '20px', color: '#727786' }} />
        <FileCard label="Target" color="#234B5F" icon={<DatabaseOutlined />} stats={targetStats} warn={alert.mismatches} loading={isFetching} isEmpty={targetEmpty} />
      </div>

      <OverviewFilePreview
        open={previewOpen && !isJson}
        preview={previewData}
        sourceLabel={sourceStats.name}
        targetLabel={targetStats.name}
        loading={previewLoading}
        error={previewError}
        onClose={() => setPreviewOpen(false)}
      />

      <OverviewJsonPreview
        open={previewOpen && isJson}
        sourcePreview={sourceProfile.profile?.json_preview ?? null}
        targetPreview={targetProfile.profile?.json_preview ?? null}
        sourceLabel={sourceStats.name}
        targetLabel={targetStats.name}
        onClose={() => setPreviewOpen(false)}
      />

      {isFixedWidth && (
        <FixedWidthLayoutPanel
          columns={form.fixedWidthColumns}
          loading={fixedWidthLoading}
          error={fixedWidthError}
          joinColumn={form.uidColumn}
          lineWidth={form.fixedWidthLineWidth ?? undefined}
          onChange={handleFixedWidthChange}
          onJoinColumnChange={handleJoinColumnChange}
        />
      )}

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px 20px', borderRadius: '8px', backgroundColor: alertStyles.backgroundColor, border: `1px solid ${alertStyles.borderColor}` }}>
        {alertStyles.icon}
        <div>
          <h5 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: 700 }}>{alert.title}</h5>
          <p style={{ margin: 0, fontSize: '13px' }}>{alert.message}</p>
        </div>
      </div>
    </div>
  );
};
