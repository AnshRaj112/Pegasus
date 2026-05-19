export function normalizeColumnName(name) {
  return String(name ?? '').trim().toLowerCase().replace(/\s+/g, '')
}

export function buildMappingRows(sourceColumns, targetColumns, previousRows = [], autoMappings = []) {
  const previousBySource = new Map(previousRows.map(row => [row.sourceCol, row]))
  const autoBySource = new Map(autoMappings.map(row => [row.source_column, row.target_column]))

  return sourceColumns.map((sourceCol, index) => {
    const previous = previousBySource.get(sourceCol)
    const previousTarget = previous?.targetCol && targetColumns.includes(previous.targetCol) ? previous.targetCol : ''
    const autoTarget = autoBySource.get(sourceCol) ?? ''

    return {
      id: sourceCol,
      sourceCol,
      targetCol: previousTarget || autoTarget,
      color: previous?.color ?? ROW_COLORS[index % ROW_COLORS.length],
    }
  })
}

export function toColumnMappingPayload(rows) {
  return rows
    .filter(row => row.targetCol)
    .map(row => ({
      source_column: row.sourceCol,
      target_column: row.targetCol,
    }))
}

export function countMappedRows(rows) {
  return rows.filter(row => row.targetCol).length
}

const ROW_COLORS = [
  '#f97316', '#3b82f6', '#22c55e', '#a855f7', '#ec4899',
  '#14b8a6', '#eab308', '#ef4444', '#6366f1', '#84cc16',
]