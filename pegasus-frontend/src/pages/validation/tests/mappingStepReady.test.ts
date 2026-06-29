import { describe, expect, it } from 'vitest';

import { resolveMappingStepReady } from '../mappingStepReady';
import { initialState } from '../Validation.reducer';
import {
  mockSourceCloud,
  mockSourceProfile,
  mockTargetCloud,
  mockTargetProfile,
  validationFormWithFiles,
} from '../Validation.mockData';

describe('resolveMappingStepReady', () => {
  const baseForm = validationFormWithFiles;

  it('reports loading until tabular preview data is available', () => {
    const status = resolveMappingStepReady({
      form: baseForm,
      cache: null,
      previewColumnsState: { pairKey: null, data: null, isFetching: true, error: null },
      previewFixedWidthState: initialState.previewFixedWidthState,
      isJson: false,
      isArchiveMetadataOnly: false,
      isFixedWidth: false,
    });

    expect(status.loading).toBe(true);
    expect(status.ready).toBe(false);
  });

  it('reports ready when tabular column mappings are hydrated', () => {
    const sourceKey = 'conn-1:test-bucket:data/source.csv';
    const targetKey = 'conn-1:test-bucket:data/target.csv';
    const pairKey = `${sourceKey}|${targetKey}|id|auto|true`;

    const status = resolveMappingStepReady({
      form: {
        ...baseForm,
        columnMappings: [{ source_column: 'id', target_column: 'id' }],
      },
      cache: null,
      previewColumnsState: {
        pairKey,
        data: { source_columns: ['id'], target_columns: ['id'] } as never,
        isFetching: false,
        error: null,
      },
      previewFixedWidthState: initialState.previewFixedWidthState,
      isJson: false,
      isArchiveMetadataOnly: false,
      isFixedWidth: false,
    });

    expect(status.loading).toBe(false);
    expect(status.ready).toBe(true);
  });

  it('reports ready for archive metadata when overview profiles are cached', () => {
    const sourceKey = 'conn-1:test-bucket:archives/source.zip';
    const targetKey = 'conn-1:test-bucket:archives/target.zip';

    const status = resolveMappingStepReady({
      form: {
        ...baseForm,
        sourceCloud: { ...mockSourceCloud, object_name: 'archives/source.zip' },
        targetCloud: { ...mockTargetCloud, object_name: 'archives/target.zip' },
      },
      cache: {
        sourceKey,
        targetKey,
        source: mockSourceProfile,
        target: mockTargetProfile,
        sourceError: false,
        targetError: false,
      },
      previewColumnsState: initialState.previewColumnsState,
      previewFixedWidthState: initialState.previewFixedWidthState,
      isJson: false,
      isArchiveMetadataOnly: true,
      isFixedWidth: false,
    });

    expect(status.loading).toBe(false);
    expect(status.ready).toBe(true);
  });
});
