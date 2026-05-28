import { buildMappingRows } from '../components/mapping/columnMapping'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

function absoluteApiUrl(pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl
  const base = apiBase.replace(/\/$/, '')
  const path = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`
  return base ? `${base}${path}` : path
}

function formatDetail(detail) {
  if (detail == null) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map(e => (typeof e === 'object' && e != null ? e.msg ?? e.message : null) ?? JSON.stringify(e)).join('; ')
  }
  return JSON.stringify(detail)
}

export function buildColumnPreviewRequestBody(unit, options) {
  const {
    sourceStorageType,
    targetStorageType,
    sourceCloudConfig,
    targetCloudConfig,
    uidColumn,
    delimiter,
    hasHeader,
    headerLeadingRows,
  } = options

  if (sourceStorageType === 'cloud') {
    return {
      source_cloud: {
        provider: 'google-cloud-storage',
        bucket: sourceCloudConfig.bucket,
        object_name: unit.sourcePaths[0],
        credentials_json: sourceCloudConfig.credentialsJson,
        project_id: sourceCloudConfig.projectId || undefined,
      },
      target_cloud: {
        provider: 'google-cloud-storage',
        bucket: targetCloudConfig?.bucket || sourceCloudConfig.bucket,
        object_name: unit.targetPaths[0],
        credentials_json: targetCloudConfig?.credentialsJson || sourceCloudConfig.credentialsJson,
        project_id: targetCloudConfig?.projectId || sourceCloudConfig.projectId || undefined,
      },
      uid_column: (uidColumn || 'id').trim(),
      delimiter: (delimiter || 'auto').trim(),
      has_header: hasHeader,
      header_leading_rows: headerLeadingRows ?? 0,
    }
  }

  return {
    source_path: unit.sourcePaths[0],
    target_path: unit.targetPaths[0],
    uid_column: (uidColumn || 'id').trim(),
    delimiter: (delimiter || 'auto').trim(),
    has_header: hasHeader,
    header_leading_rows: headerLeadingRows ?? 0,
  }
}

export async function fetchUnitColumnPreview(unit, options) {
  const res = await fetch(absoluteApiUrl('/api/v1/validate/local/columns'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildColumnPreviewRequestBody(unit, options)),
  })
  const raw = await res.text()
  let data = {}
  if (raw) {
    try { data = JSON.parse(raw) } catch { throw new Error(raw.trim().slice(0, 500)) }
  }
  if (!res.ok) throw new Error(formatDetail(data.detail) || `${res.status} ${res.statusText}`)
  return data
}

/**
 * Apply a shared template mapping to one file pair's column preview.
 * Returns unit config plus mismatch issues when columns cannot be aligned.
 */
export function adaptTemplateToUnit(template, previewApiData) {
  const uid = String(template.uidColumn || '').trim()
  const sourceColumns = Array.isArray(previewApiData.source_columns) ? previewApiData.source_columns : []
  const targetColumns = Array.isArray(previewApiData.target_columns) ? previewApiData.target_columns : []
  const compareColumns = Array.isArray(previewApiData.compare_columns)
    ? previewApiData.compare_columns
    : sourceColumns.filter(col => col !== uid)
  const autoMappings = Array.isArray(previewApiData.auto_mappings) ? previewApiData.auto_mappings : []
  const issues = []

  if (!uid) {
    issues.push('Template is missing a UID column')
  } else {
    if (!sourceColumns.includes(uid)) issues.push(`UID column "${uid}" is not in the source file`)
    if (!targetColumns.includes(uid)) issues.push(`UID column "${uid}" is not in the target file`)
  }

  const templateRows = Array.isArray(template.mappings) ? template.mappings : []
  const mappedTemplateRows = templateRows.filter(
    row => row.targetCol || (Array.isArray(row.targetCols) && row.targetCols.length > 0),
  )

  if (mappedTemplateRows.length === 0) {
    issues.push('Template has no column mappings defined')
  }

  for (const row of mappedTemplateRows) {
    if (!sourceColumns.includes(row.sourceCol)) {
      issues.push(`Source column "${row.sourceCol}" is missing in this file`)
    }
    const targets = [
      row.targetCol,
      ...(Array.isArray(row.targetCols) ? row.targetCols : []),
    ].map(t => String(t || '').trim()).filter(Boolean)
    const uniqueTargets = [...new Set(targets)]
    for (const tgt of uniqueTargets) {
      if (!targetColumns.includes(tgt)) {
        issues.push(`Target column "${tgt}" (for source "${row.sourceCol}") is missing in this file`)
      }
    }
  }

  const targetColsNoUid = targetColumns.filter(col => col !== uid)
  const mappings = buildMappingRows(
    compareColumns.length ? compareColumns : sourceColumns.filter(col => col !== uid),
    targetColsNoUid,
    templateRows,
    autoMappings,
  )

  const columnPreview = {
    sourceColumns,
    targetColumns,
    compareColumns,
    autoMappings,
    unmatchedSourceColumns: Array.isArray(previewApiData.unmatched_source_columns)
      ? previewApiData.unmatched_source_columns
      : [],
    unmatchedTargetColumns: Array.isArray(previewApiData.unmatched_target_columns)
      ? previewApiData.unmatched_target_columns
      : [],
    delimiter: previewApiData.delimiter || template.delimiter || 'auto',
    sourceSamples: previewApiData.source_samples && typeof previewApiData.source_samples === 'object'
      ? previewApiData.source_samples
      : {},
    targetSamples: previewApiData.target_samples && typeof previewApiData.target_samples === 'object'
      ? previewApiData.target_samples
      : {},
    sampleRowCount: Number(previewApiData.sample_row_count) || 6,
  }

  const unitConfig = {
    mappings,
    uidColumn: uid,
    delimiter: template.delimiter || columnPreview.delimiter || 'auto',
    hasHeader: template.hasHeader !== false,
    validateHeaderFormats: template.validateHeaderFormats || false,
    validateFooters: template.validateFooters || false,
    footerTrailingRows: template.footerTrailingRows ?? 1,
    headerLeadingRows: template.headerLeadingRows ?? 0,
    testMode: template.testMode || 'full',
    uidGte: template.uidGte || '',
    columnPreview,
    formatChecks: [],
    footerValidation: null,
  }

  const hasMismatch = issues.length > 0
    || !mappings.some(row => String(row.targetCol || '').trim())

  return { unitConfig, issues, hasMismatch }
}

export function buildCsvTemplateSnapshot({
  mappings,
  uidColumn,
  delimiter,
  hasHeader,
  validateHeaderFormats,
  validateFooters,
  footerTrailingRows,
  headerLeadingRows,
  testMode,
  uidGte,
  columnPreview,
}) {
  return {
    format: 'csv',
    mappings: mappings.map(row => ({ ...row, targetCols: [...(row.targetCols || [])] })),
    uidColumn,
    delimiter,
    hasHeader,
    validateHeaderFormats,
    validateFooters,
    footerTrailingRows,
    headerLeadingRows,
    testMode: testMode || 'full',
    uidGte: uidGte || '',
    columnPreview: columnPreview ? { ...columnPreview } : null,
  }
}

export function buildFixedWidthTemplateSnapshot({
  fwColumns,
  fwJoinColumn,
  fwMatchStrategy,
  fwDateColumn,
  sourceDateStart,
  sourceDateEnd,
  sourceDateFormat,
  targetDateStart,
  targetDateEnd,
  targetDateFormat,
}) {
  return {
    format: 'fixed-width',
    fwColumns: (fwColumns || []).map(col => ({ ...col })),
    fwJoinColumn,
    fwMatchStrategy,
    fwDateColumn,
    sourceDateStart,
    sourceDateEnd,
    sourceDateFormat,
    targetDateStart,
    targetDateEnd,
    targetDateFormat,
  }
}

export function buildJsonTemplateSnapshot() {
  return { format: 'json' }
}

/** @deprecated Use buildCsvTemplateSnapshot */
export function buildTemplateSnapshot(opts) {
  return buildCsvTemplateSnapshot(opts)
}

export async function fetchUnitFixedWidthLayout(unit) {
  const params = new URLSearchParams({
    source_path: unit.sourcePaths[0],
    target_path: unit.targetPaths[0],
  })
  const res = await fetch(absoluteApiUrl(`/api/v1/validate/local/fixed-width/columns?${params}`))
  const raw = await res.text()
  let data = {}
  if (raw) {
    try { data = JSON.parse(raw) } catch { throw new Error(raw.trim().slice(0, 500)) }
  }
  if (!res.ok) throw new Error(formatDetail(data.detail) || `${res.status} ${res.statusText}`)
  return data
}

export function adaptFixedWidthTemplateToUnit(template, layoutData) {
  const detected = Array.isArray(layoutData.columns) ? layoutData.columns : []
  const detectedByName = Object.fromEntries(detected.map(col => [col.field_name, col]))
  const templateColumns = Array.isArray(template.fwColumns) ? template.fwColumns : []
  const issues = []

  const join = String(template.fwJoinColumn || '').trim()
  if (!join) {
    issues.push('Template is missing a join column')
  } else if (!detectedByName[join]) {
    issues.push(`Join column "${join}" is not in this file pair`)
  }

  const dateName = String(template.fwDateColumn || '').trim()
  if (dateName && !detectedByName[dateName]) {
    issues.push(`Date column "${dateName}" is not in this file pair`)
  }

  if (templateColumns.length === 0) {
    issues.push('Template has no fixed-width fields defined')
  }

  for (const col of templateColumns) {
    const name = col.field_name
    if (!detectedByName[name]) {
      issues.push(`Field "${name}" is not in this file pair`)
    }
  }

  const fwColumns = templateColumns
    .map(tc => detectedByName[tc.field_name])
    .filter(Boolean)

  if (fwColumns.length !== templateColumns.length && templateColumns.length > 0) {
    issues.push('One or more template fields could not be aligned to this file')
  }

  const dcol = dateName ? fwColumns.find(c => c.field_name === dateName) : null

  const unitConfig = {
    fwColumns,
    fwJoinColumn: join || detected[0]?.field_name || 'id',
    fwMatchStrategy: template.fwMatchStrategy || 'fuzzy',
    fwDateColumn: dateName || templateColumns[templateColumns.length - 1]?.field_name || 'dob',
    sourceDateStart: dcol ? Number(dcol.source_start) : template.sourceDateStart,
    sourceDateEnd: dcol ? Number(dcol.source_end) : template.sourceDateEnd,
    sourceDateFormat: template.sourceDateFormat || 'dd/mm/yyyy',
    targetDateStart: dcol ? Number(dcol.target_start) : template.targetDateStart,
    targetDateEnd: dcol ? Number(dcol.target_end) : template.targetDateEnd,
    targetDateFormat: template.targetDateFormat || 'yyyy/mm/dd',
    fwSourceSample: layoutData.source_sample || '',
    fwTargetSample: layoutData.target_sample || '',
  }

  const hasMismatch = issues.length > 0
    || fwColumns.length === 0
    || (templateColumns.length > 0 && fwColumns.length < templateColumns.length)

  return { unitConfig, issues, hasMismatch }
}

export async function applyCsvTemplateToAllUnits(units, template, previewOptions) {
  const unitConfigs = {}
  const mismatchUnitIds = []
  const mismatchDetails = {}

  for (const unit of units) {
    const preview = await fetchUnitColumnPreview(unit, {
      ...previewOptions,
      uidColumn: template.uidColumn,
      delimiter: template.delimiter,
      hasHeader: template.hasHeader,
      headerLeadingRows: template.headerLeadingRows ?? 0,
    })
    const { unitConfig, issues, hasMismatch } = adaptTemplateToUnit(template, preview)
    unitConfigs[unit.unitId] = unitConfig
    if (hasMismatch) {
      mismatchUnitIds.push(unit.unitId)
      mismatchDetails[unit.unitId] = issues
    }
  }

  return { unitConfigs, mismatchUnitIds, mismatchDetails }
}

export async function applyFixedWidthTemplateToAllUnits(units, template) {
  const unitConfigs = {}
  const mismatchUnitIds = []
  const mismatchDetails = {}

  for (const unit of units) {
    const layout = await fetchUnitFixedWidthLayout(unit)
    const { unitConfig, issues, hasMismatch } = adaptFixedWidthTemplateToUnit(template, layout)
    unitConfigs[unit.unitId] = unitConfig
    if (hasMismatch) {
      mismatchUnitIds.push(unit.unitId)
      mismatchDetails[unit.unitId] = issues
    }
  }

  return { unitConfigs, mismatchUnitIds, mismatchDetails }
}

export function applyJsonTemplateToAllUnits(units) {
  const unitConfigs = {}
  for (const unit of units) {
    unitConfigs[unit.unitId] = { jsonConfigured: true }
  }
  return {
    unitConfigs,
    mismatchUnitIds: [],
    mismatchDetails: {},
  }
}

export async function applyTemplateToAllUnits(units, template, previewOptions, fileFormat) {
  if (fileFormat === 'fixed-width') {
    return applyFixedWidthTemplateToAllUnits(units, template)
  }
  if (fileFormat === 'json') {
    return applyJsonTemplateToAllUnits(units)
  }
  return applyCsvTemplateToAllUnits(units, template, previewOptions)
}
