const apiBase = (import.meta as any).env.VITE_API_BASE ?? ''

function absoluteApiUrl(pathOrUrl: string | undefined): string | undefined {
  if (!pathOrUrl) return pathOrUrl
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl
  const base = apiBase.replace(/\/$/, '')
  const path = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`
  return base ? `${base}${path}` : path
}

export function newUnitId(): string {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `unit-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export async function matchFilePairs({
  sourceDirectory,
  targetDirectory,
  fileFormat,
  recursive,
}: {
  sourceDirectory: string
  targetDirectory: string
  fileFormat: string
  recursive: boolean
}): Promise<any> {
  const res = await fetch(absoluteApiUrl('/api/v1/validate/local/match-pairs')!, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_directory: sourceDirectory,
      target_directory: targetDirectory,
      file_format: fileFormat,
      recursive: Boolean(recursive),
    }),
  })
  const payload = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = payload.detail
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return payload
}

export function unitsFromPairs(pairs: any[]): any[] {
  return pairs.map(pair => ({
    unitId: pair.unit_id,
    sourcePaths: [pair.source_path],
    targetPaths: [pair.target_path],
    label: pair.source_name || pair.source_path.split('/').pop(),
    autoMatched: pair.auto_matched,
  }))
}

export function unitFromMerge({ sourcePaths, targetPaths, label }: any): any {
  return {
    unitId: newUnitId(),
    sourcePaths,
    targetPaths,
    label: label || 'Merged validation',
    autoMatched: false,
  }
}

export function buildBatchValidatePayload({
  fileFormat,
  units,
  unitConfigs,
  onUnitFailure,
  delimiter,
  hasHeader,
  validateHeaderFormats,
  validateFooters,
  footerTrailingRows,
  headerLeadingRows,
  fixedWidthConfigBuilder,
  cloudBucket,
  cloudCredentialsJson,
  cloudProjectId,
  testMode,
  uidGte,
}: any): any {
  const payload: any = {
    file_format: fileFormat,
    on_unit_failure: onUnitFailure,
    delimiter: delimiter?.trim() || 'auto',
    has_header: hasHeader,
    header_leading_rows: headerLeadingRows ?? 0,
    validate_header_formats: validateHeaderFormats,
    validate_footers: validateFooters,
    footer_trailing_rows: footerTrailingRows,
    test_mode: testMode || 'full',
    uid_gte: uidGte?.trim() || undefined,
    units: units.map((unit: any) => {
      const cfg = unitConfigs[unit.unitId] || {}
      const base: any = {
        unit_id: unit.unitId,
        source_paths: unit.sourcePaths,
        target_paths: unit.targetPaths,
        uid_column: (cfg.uidColumn || 'id').trim(),
        column_mappings: cfg.columnMappings || [],
      }
      if (fileFormat === 'fixed-width' && typeof fixedWidthConfigBuilder === 'function') {
        return { ...base, fixed_width_config: fixedWidthConfigBuilder(cfg) }
      }
      return base
    }),
  }
  if (cloudBucket && cloudCredentialsJson) {
    payload.cloud_bucket = cloudBucket
    payload.cloud_credentials_json = cloudCredentialsJson
    payload.cloud_project_id = cloudProjectId || undefined
  }
  return payload
}

export function normalizeBatchPollResult(data: any): any {
  if (data?.batch_result) return data.batch_result
  return null
}
