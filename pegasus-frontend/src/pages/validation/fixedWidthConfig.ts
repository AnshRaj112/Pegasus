import type { FixedWidthColumnPreview, FixedWidthConfig } from '../../shared/api/Api';

export const fixedWidthConfigFromColumns = (
  columns: FixedWidthColumnPreview[],
  uidColumn: string,
): FixedWidthConfig => ({
  uid_column: uidColumn,
  fields: columns.map((col) => ({
    field_name: col.field_name,
    source_start: col.source_start,
    source_end: col.source_end,
    target_start: col.target_start,
    target_end: col.target_end,
    field_type: col.field_type,
    structured_order_sensitive: col.structured_order_sensitive ?? false,
    date_format: col.date_format ?? undefined,
    source_date_format: col.source_date_format ?? col.date_format ?? undefined,
    target_date_format: col.target_date_format ?? col.date_format ?? undefined,
    compare_enabled: col.compare_enabled !== false,
    is_sensitive: col.is_sensitive ?? false,
    source_regex_pattern: col.source_regex_pattern ?? undefined,
    source_regex_replacement: col.source_regex_replacement ?? '',
    target_regex_pattern: col.target_regex_pattern ?? undefined,
    target_regex_replacement: col.target_regex_replacement ?? '',
  })),
  match_strategy: 'exact',
});
