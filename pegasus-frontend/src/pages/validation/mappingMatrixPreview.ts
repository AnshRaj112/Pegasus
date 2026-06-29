import type { ColumnMapping, LocalColumnPreviewResponse } from '../../shared/api/Api';

export type MappingMatrixRow = {
  id: string;
  sourceCol: string;
  sourceType: string;
  targetCols: { name: string; type: string; sample: string }[];
  isPk: boolean;
  isIgnored: boolean;
  isSensitive: boolean;
  isExpanded: boolean;
  isOrderSensitive: boolean;
  sourceExpr: string;
  targetExpr: string;
  previewValue: string;
};

const looksStructured = (value: string): boolean => {
  const s = value.trim();
  return s.length > 0 && /^[\[{]/.test(s);
};

const inferType = (value: string, isComplex: boolean): string => {
  if (isComplex || looksStructured(value)) return 'Structured';
  if (/^(true|false)$/i.test(value)) return 'Bool';
  if (/^-?\d+$/.test(value)) return 'Int';
  if (/^-?\d+\.\d+$/.test(value)) return 'Float';
  return 'String';
};

export const targetSamplesFromPreview = (
  preview: LocalColumnPreviewResponse,
): Record<string, string> => {
  const samples: Record<string, string> = {};
  Object.entries(preview.target_samples ?? {}).forEach(([key, values]) => {
    samples[key] = values[0] ?? '';
  });
  return samples;
};

export const buildMatrixFromColumnPreview = (
  preview: LocalColumnPreviewResponse,
  uidColumn: string,
): { rows: MappingMatrixRow[]; targetSamples: Record<string, string> } => {
  const savedUids = uidColumn.split(',').map((s) => s.trim()).filter(Boolean);
  const defaultUid = preview.source_columns.includes('column_1')
    ? 'column_1'
    : preview.source_columns[0] ?? 'id';
  const isUidMatch = (col: string) => savedUids.includes(col)
    || (savedUids.length === 0 && col === defaultUid);

  const autoMappings = preview.auto_mappings ?? [];
  const complex = preview.complex_columns ?? [];
  const targetSamples = targetSamplesFromPreview(preview);

  const rows: MappingMatrixRow[] = preview.source_columns.map((col) => {
    const auto = autoMappings.find((mapping) => mapping.source_column === col);
    const isUid = isUidMatch(col);
    const uidTarget = isUid && preview.target_columns.includes(col) ? col : null;
    const targets = auto ? [auto.target_column] : uidTarget ? [uidTarget] : [];
    const sample = preview.source_samples?.[col]?.[0] ?? '';

    return {
      id: col,
      sourceCol: col,
      sourceType: inferType(sample, complex.includes(col)),
      targetCols: targets.map((target) => ({
        name: target,
        type: inferType(targetSamples[target] ?? '', false),
        sample: targetSamples[target] ?? '',
      })),
      isPk: isUid,
      isIgnored: false,
      isSensitive: false,
      isExpanded: false,
      isOrderSensitive: false,
      sourceExpr: '',
      targetExpr: '',
      previewValue: sample,
    };
  });

  return { rows, targetSamples };
};

export const applySavedColumnMappingsToMatrix = (
  rows: MappingMatrixRow[],
  savedMappings: ColumnMapping[],
  uidColumn: string,
): MappingMatrixRow[] => {
  if (savedMappings.length === 0) return rows;

  const uidSet = new Set(uidColumn.split(',').map((s) => s.trim()).filter(Boolean));
  const savedBySource = new Map(savedMappings.map((mapping) => [mapping.source_column, mapping]));

  return rows.map((row) => {
    const saved = savedBySource.get(row.sourceCol);
    if (!saved) {
      return {
        ...row,
        isPk: uidSet.has(row.sourceCol),
        isIgnored: true,
        targetCols: [],
      };
    }

    const targets = [saved.target_column, ...(saved.target_columns ?? [])].filter(Boolean);
    const isStructured = saved.compare_mode === 'structured';

    return {
      ...row,
      sourceType: isStructured ? 'Structured' : row.sourceType,
      targetCols: targets.map((name) => {
        const existing = row.targetCols.find((target) => target.name === name);
        return existing ?? { name, type: 'String', sample: '' };
      }),
      isPk: uidSet.has(row.sourceCol),
      isIgnored: false,
      isSensitive: Boolean(saved.is_sensitive),
      isOrderSensitive: saved.structured_order_sensitive ?? false,
      sourceExpr: saved.source_regex_pattern ?? '',
      targetExpr: saved.target_regex_pattern ?? '',
    };
  });
};

export const enrichMatrixWithPreviewSamples = (
  rows: MappingMatrixRow[],
  preview: LocalColumnPreviewResponse,
): MappingMatrixRow[] => {
  const targetSamples = targetSamplesFromPreview(preview);
  const complex = preview.complex_columns ?? [];

  return rows.map((row) => {
    const sample = preview.source_samples?.[row.sourceCol]?.[0] ?? row.previewValue;
    return {
      ...row,
      previewValue: sample,
      sourceType: row.sourceType === 'Structured'
        ? row.sourceType
        : inferType(sample, complex.includes(row.sourceCol)),
      targetCols: row.targetCols.map((target) => ({
        ...target,
        type: target.type === 'Structured'
          ? target.type
          : inferType(targetSamples[target.name] ?? target.sample, false),
        sample: targetSamples[target.name] ?? target.sample,
      })),
    };
  });
};
