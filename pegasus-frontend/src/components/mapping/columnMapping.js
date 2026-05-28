export function normalizeColumnName(name) {
  return String(name ?? '').trim().toLowerCase().replace(/\s+/g, '')
}

const DEFAULT_COMPARE = {
  compareMode: 'auto',
  structuredOrderSensitive: false,
  customExpression: '',
  sourceDateFormat: '',
  targetDateFormat: '',
  sourceStripPrefix: '',
  targetStripPrefix: '',
  sourceRegexPattern: '',
  sourceRegexReplacement: '',
  targetRegexPattern: '',
  targetRegexReplacement: '',
}

export function buildMappingRows(sourceColumns, targetColumns, previousRows = [], autoMappings = []) {
  const previousBySource = new Map(previousRows.map(row => [row.sourceCol, row]))
  const autoBySource = new Map(autoMappings.map(row => [row.source_column, row.target_column]))

  return sourceColumns.map((sourceCol, index) => {
    const previous = previousBySource.get(sourceCol)
    const previousTarget = previous?.targetCol && targetColumns.includes(previous.targetCol) ? previous.targetCol : ''
    const previousTargets = Array.isArray(previous?.targetCols)
      ? previous.targetCols.filter(col => targetColumns.includes(col))
      : []
    const autoTarget = autoBySource.get(sourceCol) ?? ''
    const initialTargets = previousTarget
      ? [previousTarget, ...previousTargets.filter(col => col !== previousTarget)]
      : previousTargets.length > 0
      ? previousTargets
      : autoTarget
      ? [autoTarget]
      : []

    return {
      id: sourceCol,
      sourceCol,
      targetCol: initialTargets[0] ?? '',
      targetCols: initialTargets,
      color: previous?.color ?? ROW_COLORS[index % ROW_COLORS.length],
      compareMode: previous?.compareMode ?? DEFAULT_COMPARE.compareMode,
      structuredOrderSensitive: previous?.structuredOrderSensitive ?? DEFAULT_COMPARE.structuredOrderSensitive,
      customExpression: previous?.customExpression ?? '',
      sourceDateFormat: previous?.sourceDateFormat ?? '',
      targetDateFormat: previous?.targetDateFormat ?? '',
      sourceStripPrefix: previous?.sourceStripPrefix ?? '',
      targetStripPrefix: previous?.targetStripPrefix ?? '',
      sourceRegexPattern: previous?.sourceRegexPattern ?? '',
      sourceRegexReplacement: previous?.sourceRegexReplacement ?? '',
      targetRegexPattern: previous?.targetRegexPattern ?? '',
      targetRegexReplacement: previous?.targetRegexReplacement ?? '',
    }
  })
}

function optionalField(value) {
  const trimmed = String(value ?? '').trim()
  return trimmed || undefined
}

export function toColumnMappingPayload(rows) {
  return rows
    .filter(row => row.targetCol)
    .map(row => {
      const payload = {
        source_column: row.sourceCol,
        target_column: row.targetCol,
      }
      const additionalTargets = Array.isArray(row.targetCols)
        ? row.targetCols.map(col => String(col ?? '').trim()).filter(Boolean)
        : []
      if (additionalTargets.length > 0) {
        payload.target_columns = additionalTargets
      }
      const mode = String(row.compareMode || 'auto').trim() || 'auto'
      if (mode !== 'auto') payload.compare_mode = mode
      if (mode === 'structured' && row.structuredOrderSensitive) {
        payload.structured_order_sensitive = true
      }
      const customExpression = optionalField(row.customExpression)
      if (customExpression) payload.custom_expression = customExpression
      const srcFmt = optionalField(row.sourceDateFormat)
      const tgtFmt = optionalField(row.targetDateFormat)
      const srcPrefix = optionalField(row.sourceStripPrefix)
      const tgtPrefix = optionalField(row.targetStripPrefix)
      const srcPat = optionalField(row.sourceRegexPattern)
      const tgtPat = optionalField(row.targetRegexPattern)
      if (srcFmt) payload.source_date_format = srcFmt
      if (tgtFmt) payload.target_date_format = tgtFmt
      if (srcPrefix) payload.source_strip_prefix = srcPrefix
      if (tgtPrefix) payload.target_strip_prefix = tgtPrefix
      if (srcPat) {
        payload.source_regex_pattern = srcPat
        payload.source_regex_replacement = row.sourceRegexReplacement ?? ''
      }
      if (tgtPat) {
        payload.target_regex_pattern = tgtPat
        payload.target_regex_replacement = row.targetRegexReplacement ?? ''
      }
      return payload
    })
}

export function mappingRowFromApi(mapping) {
  const targetColumns = Array.isArray(mapping.target_columns)
    ? mapping.target_columns.map(col => String(col ?? '').trim()).filter(Boolean)
    : []
  const primaryTarget = String(mapping.target_column ?? '').trim()
  return {
    sourceCol: mapping.source_column,
    targetCol: primaryTarget,
    targetCols: primaryTarget
      ? [primaryTarget, ...targetColumns.filter(col => col !== primaryTarget)]
      : targetColumns,
    compareMode: mapping.compare_mode || 'auto',
    structuredOrderSensitive: Boolean(mapping.structured_order_sensitive),
    customExpression: mapping.custom_expression || '',
    sourceDateFormat: mapping.source_date_format || '',
    targetDateFormat: mapping.target_date_format || '',
    sourceStripPrefix: mapping.source_strip_prefix || '',
    targetStripPrefix: mapping.target_strip_prefix || '',
    sourceRegexPattern: mapping.source_regex_pattern || '',
    sourceRegexReplacement: mapping.source_regex_replacement || '',
    targetRegexPattern: mapping.target_regex_pattern || '',
    targetRegexReplacement: mapping.target_regex_replacement || '',
  }
}

export function countMappedRows(rows) {
  return rows.filter(row => row.targetCol || (Array.isArray(row.targetCols) && row.targetCols.length > 0)).length
}

export function mappingHasCustomRule(row) {
  if (!row) return false
  const mode = String(row.compareMode || 'auto').trim() || 'auto'
  if (mode === 'structured' && row.structuredOrderSensitive) return true
  if (mode !== 'auto') return true
  return Boolean(
    row.customExpression?.trim()
    ||
    row.sourceDateFormat?.trim()
    || row.targetDateFormat?.trim()
    || row.sourceStripPrefix?.trim()
    || row.targetStripPrefix?.trim()
    || row.sourceRegexPattern?.trim()
    || row.targetRegexPattern?.trim(),
  )
}

export function clearCompareRule(row) {
  return {
    ...row,
    ...DEFAULT_COMPARE,
  }
}

const ROW_COLORS = [
  '#f97316', '#3b82f6', '#22c55e', '#a855f7', '#ec4899',
  '#14b8a6', '#eab308', '#ef4444', '#6366f1', '#84cc16',
]
