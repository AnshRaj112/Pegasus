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

function buildStoragePayload(prefix, { storageType, path, cloudConfig }) {
  if (storageType === 'cloud') {
    const normalizedProvider = String(cloudConfig?.provider || 'google-cloud-storage').trim() || 'google-cloud-storage'
    const connectionId = String(cloudConfig?.connectionId || '').trim()
    const credentialsJson = String(cloudConfig?.credentialsJson || '')
    return {
      [`${prefix}_cloud`]: {
        provider: normalizedProvider,
        connection_id: connectionId || undefined,
        bucket: String(cloudConfig?.bucket || '').trim() || undefined,
        object_name: String(cloudConfig?.objectName || '').trim(),
        credentials_json: credentialsJson || undefined,
        project_id: String(cloudConfig?.projectId || '').trim() || undefined,
      },
    }
  }

  return {
    [`${prefix}_path`]: String(path || '').trim(),
  }
}

export function buildAnalyzePayload({
  sourceStorageType,
  sourcePath,
  sourceCloudConfig,
  targetStorageType,
  targetPath,
  targetCloudConfig,
  uidColumn,
  delimiter,
  mappings,
  validateHeaderFormats,
  validateFooters,
  footerTrailingRows,
  headerLeadingRows,
  hasHeader = true,
}) {
  return {
    ...buildStoragePayload('source', { storageType: sourceStorageType, path: sourcePath, cloudConfig: sourceCloudConfig }),
    ...buildStoragePayload('target', { storageType: targetStorageType, path: targetPath, cloudConfig: targetCloudConfig }),
    uid_column: uidColumn.trim(),
    delimiter: delimiter.trim() || 'auto',
    column_mappings: mappings
      .filter(row => row.targetCol)
      .map(row => ({ source_column: row.sourceCol, target_column: row.targetCol })),
    validate_header_formats: validateHeaderFormats,
    validate_footers: validateFooters,
    footer_trailing_rows: footerTrailingRows,
    header_leading_rows: headerLeadingRows ?? 0,
    has_header: hasHeader,
  }
}
