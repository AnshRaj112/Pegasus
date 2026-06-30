import { describe, expect, it } from 'vitest';

import {
  applySavedColumnMappingsToMatrix,
  buildMatrixFromColumnPreview,
  enrichMatrixWithPreviewSamples,
} from '../mappingMatrixPreview';
import type { LocalColumnPreviewResponse } from '../../../shared/api/Api';

const preview: LocalColumnPreviewResponse = {
  source_columns: ['id', 'sku'],
  target_columns: ['id', 'sku'],
  compare_columns: ['sku'],
  auto_mappings: [{ source_column: 'sku', target_column: 'sku' }],
  unmatched_source_columns: ['id'],
  unmatched_target_columns: ['id'],
  delimiter: '||',
  has_header: true,
  source_samples: {
    id: ['1'],
    sku: ['SKU-001'],
  },
  target_samples: {
    id: ['99000'],
    sku: ['SKU-099000'],
  },
};

describe('mappingMatrixPreview', () => {
  it('builds rows with source and target samples from preview', () => {
    const { rows } = buildMatrixFromColumnPreview(preview, 'id');

    expect(rows.find((row) => row.sourceCol === 'sku')?.previewValue).toBe('SKU-001');
    expect(rows.find((row) => row.sourceCol === 'sku')?.targetCols[0]?.sample).toBe('SKU-099000');
  });

  it('enriches saved mappings with preview samples', () => {
    const saved = applySavedColumnMappingsToMatrix(
      buildMatrixFromColumnPreview(preview, 'id').rows,
      [{ source_column: 'sku', target_column: 'sku' }],
      'id',
    );
    const enriched = enrichMatrixWithPreviewSamples(
      saved.map((row) => ({ ...row, previewValue: '', targetCols: row.targetCols.map((t) => ({ ...t, sample: '' })) })),
      preview,
    );

    expect(enriched.find((row) => row.sourceCol === 'sku')?.previewValue).toBe('SKU-001');
    expect(enriched.find((row) => row.sourceCol === 'sku')?.targetCols[0]?.sample).toBe('SKU-099000');
  });

  it('marks unmatched saved mappings as ignored for headerless column names', () => {
    const headerlessPreview: LocalColumnPreviewResponse = {
      source_columns: ['column_1', 'column_2', 'column_3'],
      target_columns: ['column_1', 'column_2', 'column_3'],
      compare_columns: ['column_2', 'column_3'],
      auto_mappings: [
        { source_column: 'column_2', target_column: 'column_2' },
        { source_column: 'column_3', target_column: 'column_3' },
      ],
      unmatched_source_columns: ['column_1'],
      unmatched_target_columns: ['column_1'],
      delimiter: ',',
      has_header: false,
      inferred_has_header: false,
      source_samples: {
        column_1: ['ID001'],
        column_2: ['John Doe'],
        column_3: ['05/19/2026'],
      },
      target_samples: {
        column_1: ['ID001'],
        column_2: ['John Doe'],
        column_3: ['05/19/2026'],
      },
    };

    const fresh = buildMatrixFromColumnPreview(headerlessPreview, 'column_1').rows;
    expect(fresh.every((row) => !row.isIgnored)).toBe(true);
    expect(fresh.filter((row) => row.isPk)).toHaveLength(1);

    const stale = applySavedColumnMappingsToMatrix(
      fresh,
      [{ source_column: 'ID001', target_column: 'ID001' }],
      'column_1',
    );
    expect(stale.filter((row) => row.isIgnored).length).toBeGreaterThan(0);

    const remapped = applySavedColumnMappingsToMatrix(
      fresh,
      [
        { source_column: 'column_2', target_column: 'column_2' },
        { source_column: 'column_3', target_column: 'column_3' },
      ],
      'column_1',
    );
    expect(remapped.find((row) => row.sourceCol === 'column_2')?.isIgnored).toBe(false);
    expect(remapped.find((row) => row.sourceCol === 'column_3')?.isIgnored).toBe(false);
  });
});
