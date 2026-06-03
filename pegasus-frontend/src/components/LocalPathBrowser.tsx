import { useCallback, useEffect, useState } from 'react'
import { fetchLocalBrowseConfig } from '../api/validationHistory'
import { FolderOutlined, FileOutlined, ArrowUpOutlined, FolderOpenOutlined } from '@ant-design/icons'
import { Card, Input, Button, Space, Badge, Alert, Typography } from 'antd'

const { Text } = Typography

const apiBase = (import.meta as any).env.VITE_API_BASE ?? ''

function absoluteApiUrl(pathOrUrl: string | undefined): string | undefined {
  if (!pathOrUrl) return pathOrUrl
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl
  const base = apiBase.replace(/\/$/, '')
  const path = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`
  return base ? `${base}${path}` : path
}

function formatDetail(detail: any): string {
  if (detail == null) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (typeof e === 'object' && e != null ? (e.msg ?? e.message) : null) ?? JSON.stringify(e))
      .join('; ')
  }
  return JSON.stringify(detail)
}

function parentDirOfFile(filePath: string): string {
  const trimmed = (filePath || '').trim()
  if (!trimmed) return ''
  const lastSlash = trimmed.lastIndexOf('/')
  if (lastSlash <= 0) return ''
  return trimmed.slice(0, lastSlash) || ''
}

interface LocalPathBrowserProps {
  label: string
  value: string
  onChange: (val: string) => void
  disabled?: boolean
}

export default function LocalPathBrowser({ label, value, onChange, disabled }: LocalPathBrowserProps) {
  const [folderInput, setFolderInput] = useState(() => parentDirOfFile(value))
  const [listedDir, setListedDir] = useState<string | null>(null)
  const [parentPath, setParentPath] = useState<string | null>(null)
  const [entries, setEntries] = useState<any[]>([])
  const [truncated, setTruncated] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hasListed, setHasListed] = useState(false)
  const [browseHint, setBrowseHint] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchLocalBrowseConfig()
      .then((cfg) => {
        if (cancelled) return
        if (cfg?.default_browse_path) {
          setFolderInput((prev) => (prev.trim() ? prev : cfg.default_browse_path))
        }
        if (cfg?.path_remap_enabled && cfg.host_path_prefix && cfg.container_path_prefix) {
          setBrowseHint(
            `Docker: files are read at ${cfg.container_path_prefix}; paths shown use ${cfg.host_path_prefix}.`
          )
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  const loadDirectory = useCallback(async (dirPath: string) => {
    setLoading(true)
    setError('')
    try {
      const q = new URLSearchParams({ path: dirPath })
      const res = await fetch(`${absoluteApiUrl('/api/v1/validate/local/browse')}?${q}`)
      const payload = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(formatDetail(payload.detail) || `${res.status} ${res.statusText}`)
      }
      const resolved = payload.path ?? dirPath
      setListedDir(resolved)
      setFolderInput(resolved)
      setParentPath(payload.parent_path ?? null)
      setEntries(Array.isArray(payload.entries) ? payload.entries : [])
      setTruncated(Boolean(payload.truncated))
      setHasListed(true)
    } catch (e: any) {
      setError(e.message || 'Browse failed')
      setEntries([])
      setListedDir(null)
      setParentPath(null)
      setTruncated(false)
    } finally {
      setLoading(false)
    }
  }, [])

  function handleOpenFolder() {
    const p = folderInput.trim()
    if (!p) {
      setError('Enter an absolute folder path on the server')
      return
    }
    loadDirectory(p)
  }

  function handleGoUp() {
    if (parentPath) loadDirectory(parentPath)
  }

  function handleEntryClick(entry: any) {
    if (entry.is_dir) {
      loadDirectory(entry.path)
      return
    }
    onChange(entry.path)
  }

  return (
    <Card
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', flexWrap: 'wrap', gap: '8px' }}>
          <Space>
            <FolderOpenOutlined style={{ color: '#1677ff', fontSize: '18px' }} />
            <Text strong style={{ fontSize: '15px' }}>{label}</Text>
          </Space>
          {value ? (
            <code style={{ background: '#f5f5f5', padding: '2px 8px', borderRadius: '4px', fontSize: '12px' }}>
              {value}
            </code>
          ) : (
            <Text type="secondary" italic style={{ fontSize: '12px' }}>No file selected</Text>
          )}
        </div>
      }
      bordered={false}
      style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: '16px' }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'stretch' }}>
        {/* Left Control Column */}
        <div style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <Text type="secondary" style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase' }}>Server Folder Path</Text>
            <Input
              value={folderInput}
              disabled={disabled}
              onChange={(ev) => setFolderInput(ev.target.value)}
              onPressEnter={handleOpenFolder}
              placeholder="e.g. /home/Pegasus/test-data"
              style={{ marginTop: '4px' }}
            />
          </div>
          <Button
            type="primary"
            disabled={disabled || loading}
            loading={loading}
            onClick={handleOpenFolder}
            icon={<FolderOpenOutlined />}
            block
          >
            Open Folder
          </Button>

          {browseHint && (
            <Text type="secondary" style={{ fontSize: '12px' }}>{browseHint}</Text>
          )}

          {error && (
            <Alert message={error} type="error" showIcon style={{ marginTop: '8px' }} />
          )}
        </div>

        {/* Right Browser Panel */}
        {hasListed && (
          <div style={{ flex: '2 1 500px', display: 'flex', flexDirection: 'column', gap: '8px', borderLeft: '1px solid #f0f0f0', paddingLeft: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <code style={{ fontSize: '11px', color: '#6b7280', wordBreak: 'break-all' }}>
                {listedDir ?? '—'}
              </code>
              <Space>
                <Badge count={`${entries.length} items`} style={{ backgroundColor: '#1890ff' }} />
                {parentPath && (
                  <Button size="small" onClick={handleGoUp} icon={<ArrowUpOutlined />}>Up</Button>
                )}
              </Space>
            </div>

            {truncated && (
              <Alert message="Listing truncated - only first 5000 items shown" type="warning" showIcon style={{ margin: '8px 0' }} />
            )}

            <div style={{
              maxHeight: '260px',
              overflowY: 'auto',
              border: '1px solid #d9d9d9',
              borderRadius: '8px',
              padding: '12px',
              background: '#fafafa',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
              gap: '12px'
            }}>
              {entries.length === 0 ? (
                <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px 0', color: '#bfbfbf' }}>
                  Empty folder
                </div>
              ) : (
                entries.map((entry) => {
                  const isSelected = !entry.is_dir && entry.path === value
                  return (
                    <Card
                      hoverable
                      size="small"
                      key={entry.path}
                      onClick={() => handleEntryClick(entry)}
                      style={{
                        textAlign: 'center',
                        borderColor: isSelected ? '#1677ff' : '#d9d9d9',
                        background: isSelected ? '#e6f4ff' : '#ffffff',
                        cursor: 'pointer'
                      }}
                      styles={{ body: { padding: '12px 8px' } }}
                    >
                      <div style={{ fontSize: '24px', color: entry.is_dir ? '#1890ff' : '#8c8c8c', marginBottom: '8px' }}>
                        {entry.is_dir ? <FolderOutlined /> : <FileOutlined />}
                      </div>
                      <div style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        width: '100%'
                      }} title={entry.name}>
                        {entry.name}
                      </div>
                      <div style={{ fontSize: '10px', color: '#bfbfbf', marginTop: '2px' }}>
                        {entry.is_dir ? 'Folder' : 'File'}
                      </div>
                    </Card>
                  )
                })
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
