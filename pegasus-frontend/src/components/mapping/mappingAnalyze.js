export function formatCheckBySource(formatChecks = []) {
  const map = new Map()
  for (const check of formatChecks) {
    if (check?.source_column) map.set(check.source_column, check)
  }
  return map
}

export function hasFormatWarnings(formatChecks = []) {
  return formatChecks.some(c => c && c.compatible === false)
}

export function buildAnalyzePayload({
  sourcePath,
  targetPath,
  uidColumn,
  delimiter,
  mappings,
  validateHeaderFormats,
  validateFooters,
  footerTrailingRows,
}) {
  return {
    source_path: sourcePath.trim(),
    target_path: targetPath.trim(),
    uid_column: uidColumn.trim(),
    delimiter: delimiter.trim() || 'auto',
    column_mappings: mappings
      .filter(row => row.targetCol)
      .map(row => ({ source_column: row.sourceCol, target_column: row.targetCol })),
    validate_header_formats: validateHeaderFormats,
    validate_footers: validateFooters,
    footer_trailing_rows: footerTrailingRows,
  }
}