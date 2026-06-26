import React from 'react';
import { FileZipOutlined, SafetyOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useAppSelector } from '../../../redux/store';
import { formatDetectionLabel } from '../../../shared/formatDisplayLabel';
import { FormatDetectionChainLabel } from '../../../shared/FormatDetectionChainLabel';
import { archiveKindFromProfile, resolveWizardArchiveMode } from '../archiveFormat';

const formatBytes = (bytes: number | null | undefined) => {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

export const ArchiveValidationStep: React.FC = () => {
  const validationForm = useAppSelector((s) => s.validation.validationForm);
  const overviewCache = useAppSelector((s) => s.validation.overviewProfileCache);

  const archiveKind = resolveWizardArchiveMode({
    detectedFileFormat: validationForm.detectedFileFormat,
    sourceFileName: validationForm.sourceFileName,
    targetFileName: validationForm.targetFileName,
    sourceProfile: overviewCache?.source,
    targetProfile: overviewCache?.target,
  });

  const sourceProfile = overviewCache?.source;
  const targetProfile = overviewCache?.target;

  const entryCount = (profile: typeof sourceProfile) =>
    profile?.archive_entry_count ?? profile?.row_count ?? null;

  const manifestNote = (profile: typeof sourceProfile) => {
    if (profile?.archive_manifest_supported === false) {
      return 'Byte-identical comparison only (compressed wrapper)';
    }
    return 'Metadata manifest + streaming byte digest';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        padding: '16px 20px',
        backgroundColor: '#f0f9ff',
        border: '1px solid #bae6fd',
        borderRadius: '10px',
      }}
      >
        <SafetyOutlined style={{ color: '#0369a1', fontSize: '20px', marginTop: '2px' }} />
        <div>
          <div style={{ fontWeight: 600, color: '#0c4a6e', marginBottom: '4px' }}>
            Archive validation (no decompression)
          </div>
          <div style={{ fontSize: '13px', color: '#334155', lineHeight: 1.5 }}>
            Metadata manifest + streaming byte digest. Nested archives (e.g. csv inside zip
            inside tar) are expanded up to depth 3 using bounded member reads.
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {[
          { label: 'Source', name: validationForm.sourceFileName, profile: sourceProfile },
          { label: 'Target', name: validationForm.targetFileName, profile: targetProfile },
        ].map(({ label, name, profile }) => (
          <div
            key={label}
            style={{
              border: '1px solid #d9d9d9',
              borderRadius: '12px',
              padding: '20px',
              backgroundColor: '#fff',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: '#234B5F' }}>
              <FileZipOutlined />
              <span style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase' }}>{label}</span>
            </div>
            <h4 style={{ margin: '0 0 8px 0' }}>{name ?? '—'}</h4>
            <div style={{ fontSize: '13px', color: '#414755', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>
                <strong>Format:</strong>
                {' '}
                <FormatDetectionChainLabel format={profile?.file_format ?? archiveKind ?? 'zip'} />
              </div>
              <div><strong>Size:</strong> {formatBytes(profile?.file_size_bytes ?? null)}</div>
              <div><strong>Entries:</strong> {entryCount(profile) == null ? '—' : entryCount(profile)!.toLocaleString()}</div>
              <div><strong>Mode:</strong> {manifestNote(profile)}</div>
              {profile?.archive_entries_sample && profile.archive_entries_sample.length > 0 && (
                <div>
                  <strong>Sample paths:</strong>
                  <ul style={{ margin: '4px 0 0 16px', padding: 0, fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                    {profile.archive_entries_sample.slice(0, 5).map((entry) => (
                      <li key={entry}>{entry}</li>
                    ))}
                  </ul>
                </div>
              )}
              {profile?.archive_warnings?.map((warning) => (
                <div key={warning} style={{ color: '#b45309', fontSize: '12px' }}>{warning}</div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '14px 16px',
        backgroundColor: '#f0fdf4',
        border: '1px solid #bbf7d0',
        borderRadius: '8px',
        fontSize: '13px',
        color: '#166534',
      }}
      >
        <CheckCircleOutlined />
        Ready to validate
        {' '}
        {archiveKind ? formatDetectionLabel(archiveKind) : 'archive'}
        {' '}
        pair —
        {archiveKindFromProfile(sourceProfile) === archiveKindFromProfile(targetProfile)
          ? ' no column mapping required.'
          : ' confirm both sides are the same archive type.'}
      </div>
    </div>
  );
};
