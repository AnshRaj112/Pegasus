import { useCallback, useEffect, useState } from 'react'
import { browseCloudPrefix } from '../../api/cloudBrowse'

function formatObjectSize(sizeBytes) {
  const n = Number(sizeBytes)
  if (!Number.isFinite(n) || n < 0) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KiB`
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MiB`
  return `${(n / 1024 ** 3).toFixed(2)} GiB`
}

export default function Step2_CloudPicker({
  panelLabel,
  cloudConfig,
  onCloudConfigChange,
  onSelect,
  onBack,
  disabled,
  selectionMode = 'file',
  fileFormat = 'csv',
}) {
  const browseFileFormat = fileFormat === 'zip' || fileFormat === 'dat' ? 'csv' : fileFormat
  const formatLabel = fileFormat === 'zip' ? 'ZIP archive' : fileFormat === 'dat' ? 'DAT file' : fileFormat === 'fixed-width' ? 'Fixed-width' : fileFormat === 'json' ? 'JSON' : 'CSV'
  const [prefix, setPrefix] = useState('')
  const [parentPrefix, setParentPrefix] = useState(null)
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedObject, setSelectedObject] = useState(null)
  const [selectedObjects, setSelectedObjects] = useState([])
  const [hasListed, setHasListed] = useState(false)
  const [truncated, setTruncated] = useState(false)

  const canBrowse = Boolean(
    cloudConfig?.bucket?.trim()
    && (cloudConfig?.credentialsJson?.trim() || cloudConfig?.connectionId?.trim()),
  )

  const loadPrefix = useCallback(async (nextPrefix) => {
    if (!canBrowse) return
    setLoading(true)
    setError('')
    try {
      const data = await browseCloudPrefix({
        bucket: cloudConfig.bucket,
        prefix: nextPrefix ?? '',
        credentialsJson: cloudConfig.credentialsJson,
        connectionId: cloudConfig.connectionId,
        projectId: cloudConfig.projectId,
        fileFormat: browseFileFormat,
      })
      setPrefix(data.prefix ?? '')
      setParentPrefix(data.parent_prefix ?? null)
      setEntries(Array.isArray(data.entries) ? data.entries : [])
      setTruncated(Boolean(data.truncated))
      setHasListed(true)
    } catch (e) {
      setError(e.message || 'Cloud browse failed')
      setEntries([])
    } finally {
      setLoading(false)
    }
  }, [canBrowse, cloudConfig, browseFileFormat])

  useEffect(() => {
    if (canBrowse && !hasListed) loadPrefix('')
  }, [canBrowse, hasListed, loadPrefix])

  const folders = entries.filter(e => e.is_dir)
  const files = entries.filter(e => !e.is_dir)

  function handleConfirm() {
    const base = {
      kind: 'cloud',
      provider: 'google-cloud-storage',
      bucket: cloudConfig.bucket.trim(),
      credentialsJson: cloudConfig.credentialsJson,
      connectionId: cloudConfig.connectionId || '',
      projectId: cloudConfig.projectId?.trim() || '',
    }
    if (selectionMode === 'folder') {
      onSelect({ ...base, kind: 'cloud-folder', prefix })
      return
    }
    if (selectionMode === 'multi') {
      onSelect({ ...base, kind: 'cloud-files', objectNames: selectedObjects })
      return
    }
    if (selectedObject) {
      onSelect({ ...base, objectName: selectedObject })
    }
  }

  const canConfirm = selectionMode === 'folder'
    ? hasListed
    : selectionMode === 'multi'
      ? selectedObjects.length > 0
      : Boolean(selectedObject)

  const confirmLabel = selectionMode === 'folder'
    ? `Use prefix as ${panelLabel}`
    : selectionMode === 'multi'
      ? `Use ${selectedObjects.length} object(s) as ${panelLabel}`
      : `Use as ${panelLabel}`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-1)', marginBottom: 4 }}>
          Browse GCS — {panelLabel} {formatLabel}
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-3)' }}>
          {selectionMode === 'folder'
            ? `Navigate to the folder prefix that contains the ${formatLabel.toLowerCase()} files, then confirm.`
            : selectionMode === 'multi'
              ? `Select multiple objects (toggle). Order is preserved for merge.${fileFormat === 'zip' ? ' ZIP archives stay in the same frontend flow.' : fileFormat === 'dat' ? ' DAT files stay in the same frontend flow.' : ''}`
              : `Select one object in the bucket.${fileFormat === 'zip' ? ' ZIP archives stay in the same frontend flow.' : fileFormat === 'dat' ? ' DAT files stay in the same frontend flow.' : ''}`}
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <label>
          <span style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-2)', marginBottom: 6 }}>Bucket</span>
          <input
            className="input input-mono"
            value={cloudConfig.bucket}
            disabled={disabled}
            onChange={e => onCloudConfigChange({ ...cloudConfig, bucket: e.target.value })}
          />
        </label>
        <label>
          <span style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-2)', marginBottom: 6 }}>Project id (optional)</span>
          <input
            className="input input-mono"
            value={cloudConfig.projectId}
            disabled={disabled}
            onChange={e => onCloudConfigChange({ ...cloudConfig, projectId: e.target.value })}
          />
        </label>
      </div>

      <label>
        <span style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-2)', marginBottom: 6 }}>Service account JSON</span>
        <textarea
          className="input input-mono"
          rows={6}
          value={cloudConfig.credentialsJson}
          disabled={disabled}
          onChange={e => onCloudConfigChange({ ...cloudConfig, credentialsJson: e.target.value })}
          style={{ width: '100%', resize: 'vertical' }}
        />
      </label>

      {canBrowse && (
        <>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <code style={{ flex: 1, fontSize: 11, color: 'var(--text-3)', wordBreak: 'break-all' }}>
              gs://{cloudConfig.bucket}/{prefix}
            </code>
            {parentPrefix != null && (
              <button type="button" className="btn btn-secondary" style={{ height: 28, fontSize: 12 }} onClick={() => loadPrefix(parentPrefix)} disabled={loading}>
                Up
              </button>
            )}
            <button type="button" className="btn btn-primary" style={{ height: 28, fontSize: 12 }} onClick={() => loadPrefix(prefix)} disabled={loading}>
              Refresh
            </button>
          </div>

          {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}

          {truncated && (
            <div style={{ fontSize: 12, color: 'var(--warning, #b45309)' }}>
              Listing truncated — only the first 5000 entries are shown. Narrow the prefix to find a specific object.
            </div>
          )}

          {hasListed && (
            <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 8, height: 360, overflow: 'hidden' }}>
              <div style={{ minHeight: 0, border: '1px solid var(--border-1)', borderRadius: 8, overflowY: 'auto' }}>
                {folders.map(f => (
                  <button
                    key={f.path}
                    type="button"
                    onClick={() => loadPrefix(f.path)}
                    style={{
                      display: 'block', width: '100%', textAlign: 'left', padding: '8px 10px',
                      border: 'none', borderBottom: '1px solid var(--border-1)', background: 'transparent',
                      fontSize: 12, cursor: 'pointer', color: 'var(--text-2)',
                    }}
                  >
                    📁 {f.name}
                  </button>
                ))}
              </div>
              <div style={{ minHeight: 0, border: '1px solid var(--border-1)', borderRadius: 8, overflowY: 'auto', padding: 8 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 6 }}>
                  {files.map(f => {
                    const selected = selectionMode === 'multi'
                      ? selectedObjects.includes(f.path)
                      : selectedObject === f.path
                    return (
                      <button
                        key={f.path}
                        type="button"
                        onClick={() => {
                          if (selectionMode === 'multi') {
                            setSelectedObjects(prev => (
                              prev.includes(f.path) ? prev.filter(p => p !== f.path) : [...prev, f.path]
                            ))
                          } else {
                            setSelectedObject(prev => prev === f.path ? null : f.path)
                          }
                        }}
                        style={{
                          padding: 8, borderRadius: 6, fontSize: 11, cursor: 'pointer',
                          border: selected ? '1px solid var(--accent-border)' : '1px solid var(--border-1)',
                          background: selected ? 'var(--accent-muted)' : 'var(--surface-2)',
                        }}
                      >
                        <span style={{ display: 'block', wordBreak: 'break-word' }}>{f.name}</span>
                        {f.size_bytes != null && (
                          <span style={{ display: 'block', marginTop: 4, fontSize: 10, color: 'var(--text-4)' }}>
                            {formatObjectSize(f.size_bytes)}
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <button type="button" onClick={onBack} className="btn btn-ghost">Back</button>
        <button type="button" className="btn btn-primary" disabled={disabled || !canConfirm} onClick={handleConfirm}>
          {confirmLabel}
        </button>
      </div>
    </div>
  )
}
