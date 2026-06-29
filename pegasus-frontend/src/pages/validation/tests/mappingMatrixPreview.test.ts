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
});
