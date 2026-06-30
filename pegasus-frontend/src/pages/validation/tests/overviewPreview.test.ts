import { describe, expect, it } from 'vitest';

import { resolveOverviewPreviewStatus } from '../overviewPreview';
import { initialState } from '../Validation.reducer';
import { mockSourceProfile, mockTargetProfile } from '../Validation.mockData';

describe('resolveOverviewPreviewStatus', () => {
  const baseForm = initialState.validationForm;

  it('reports loading while profiles are not cached', () => {
    const status = resolveOverviewPreviewStatus({
      form: {
        ...baseForm,
        sourceCloud: { provider: 'google-cloud-storage', bucket: 'b', object_name: 'a.csv', connection_id: 'c' },
        targetCloud: { provider: 'google-cloud-storage', bucket: 'b', object_name: 'b.csv', connection_id: 'c' },
      },
      cache: null,
      previewColumnsState: initialState.previewColumnsState,
      previewFixedWidthState: initialState.previewFixedWidthState,
    });

    expect(status.loading).toBe(true);
    expect(status.ready).toBe(false);
  });

  it('reports ready when tabular preview data is available', () => {
    const sourceKey = 'c:b:a.csv';
    const targetKey = 'c:b:b.csv';
    const pairKey = `${sourceKey}|${targetKey}|id|auto|true`;

    const status = resolveOverviewPreviewStatus({
      form: {
        ...baseForm,
        sourceCloud: { provider: 'google-cloud-storage', bucket: 'b', object_name: 'a.csv', connection_id: 'c' },
        targetCloud: { provider: 'google-cloud-storage', bucket: 'b', object_name: 'b.csv', connection_id: 'c' },
        uidColumn: 'id',
        delimiter: 'auto',
        hasHeader: true,
        sourceFileSize: 1024,
        targetFileSize: 1024,
      },
      cache: {
        sourceKey,
        targetKey,
        source: mockSourceProfile,
        target: mockTargetProfile,
        sourceError: false,
        targetError: false,
      },
      previewColumnsState: {
        pairKey,
        data: {
          source_columns: ['id'],
          target_columns: ['id'],
          compare_columns: ['id'],
          auto_mappings: [],
          unmatched_source_columns: [],
          unmatched_target_columns: [],
          delimiter: ',',
          source_samples: { id: ['1'] },
          target_samples: { id: ['1'] },
        },
        isFetching: false,
        error: null,
      },
      previewFixedWidthState: initialState.previewFixedWidthState,
    });

    expect(status.kind).toBe('tabular');
    expect(status.loading).toBe(false);
    expect(status.ready).toBe(true);
  });

  it('reports profile errors instead of loading forever', () => {
    const sourceKey = 'c:b:a.csv';
    const targetKey = 'c:b:b.csv';

    const status = resolveOverviewPreviewStatus({
      form: {
        ...baseForm,
        sourceCloud: { provider: 'google-cloud-storage', bucket: 'b', object_name: 'a.csv', connection_id: 'c' },
        targetCloud: { provider: 'google-cloud-storage', bucket: 'b', object_name: 'b.csv', connection_id: 'c' },
        sourceFileSize: 1024,
        targetFileSize: 1024,
      },
      cache: {
        sourceKey,
        targetKey,
        source: null,
        target: mockTargetProfile,
        sourceError: true,
        targetError: false,
      },
      previewColumnsState: initialState.previewColumnsState,
      previewFixedWidthState: initialState.previewFixedWidthState,
    });

    expect(status.loading).toBe(false);
    expect(status.ready).toBe(false);
    expect(status.error).toMatch(/Could not profile/);
  });

  it('reports archive metadata-only preview as ready without column preview', () => {
    const sourceKey = 'c:b:bundle.zip';
    const targetKey = 'c:b:bundle2.zip';

    const status = resolveOverviewPreviewStatus({
      form: {
        ...baseForm,
        sourceCloud: { provider: 'google-cloud-storage', bucket: 'b', object_name: 'bundle.zip', connection_id: 'c' },
        targetCloud: { provider: 'google-cloud-storage', bucket: 'b', object_name: 'bundle2.zip', connection_id: 'c' },
        sourceFileSize: 1024,
        targetFileSize: 1024,
        detectedFileFormat: 'zip',
      },
      cache: {
        sourceKey,
        targetKey,
        source: {
          ...mockSourceProfile,
          suggested_file_format: 'zip',
          dataset_model: 'container',
          archive_entries_sample: ['META-INF/MANIFEST.MF'],
          file_format: 'zip',
        },
        target: {
          ...mockTargetProfile,
          suggested_file_format: 'zip',
          dataset_model: 'container',
          archive_entries_sample: ['META-INF/MANIFEST.MF'],
          file_format: 'zip',
        },
        sourceError: false,
        targetError: false,
      },
      previewColumnsState: initialState.previewColumnsState,
      previewFixedWidthState: initialState.previewFixedWidthState,
    });

    expect(status.kind).toBe('archive');
    expect(status.ready).toBe(true);
  });
});
