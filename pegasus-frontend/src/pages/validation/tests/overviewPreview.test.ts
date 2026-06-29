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
});
