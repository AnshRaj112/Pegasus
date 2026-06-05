import { useCallback, useEffect, useState } from 'react'
import { fetchLocalBrowseConfig } from '../api/validationHistory'
import { FolderOutlined, FileOutlined, ArrowUpOutlined, FolderOpenOutlined, LoadingOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Empty, Input, List, Space, Spin, Tag, Typography } from 'antd'

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
    return detail
      .map((e) => (typeof e === 'object' && e != null ? e.msg ?? e.message : null) ?? JSON.stringify(e))
      .join('; ')
  }
  return JSON.stringify(detail)
}

function parentDirOfFile(filePath) {
  const trimmed = (filePath || '').trim()
  if (!trimmed) return ''
  const lastSlash = trimmed.lastIndexOf('/')
  if (lastSlash <= 0) return ''
  return trimmed.slice(0, lastSlash) || ''
}

/**
 * Pick a server-side CSV: enter a folder path, list its contents, then click a file.
 */
export default function LocalPathBrowser({ label, value, onChange, disabled }) {
  const [folderInput, setFolderInput] = useState(() => parentDirOfFile(value))
  const [listedDir, setListedDir] = useState(null)
  const [parentPath, setParentPath] = useState(null)
  const [entries, setEntries] = useState([])
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
            `Docker: files are read at ${cfg.container_path_prefix}; paths shown use ${cfg.host_path_prefix}.`,
          )
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  const loadDirectory = useCallback(async (dirPath) => {
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
    } catch (e) {
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

  function handleEntryClick(entry) {
    if (entry.is_dir) {
      loadDirectory(entry.path)
      return
    }
    onChange(entry.path)
  }

  return (
    <Card
      style={{
        borderRadius: 24,
        border: '1px solid #E8E8E8',
        background: 'linear-gradient(135deg, #FFFDEF 0%, #FFFFFF 48%, #FFF7F7 100%)',
        boxShadow: '0 8px 24px rgba(15, 23, 42, 0.06)',
      }}
      styles={{ body: { padding: 24 } }}
    >
      <Space direction="vertical" size={20} style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'space-between', alignItems: 'flex-start' }} wrap>
          <Space align="start" size={10}>
            <FolderOpenOutlined style={{ color: '#EB4C4C', fontSize: 24, marginTop: 2 }} />
            <Space direction="vertical" size={2}>
              <Typography.Title level={5} style={{ margin: 0 }}>
                {label}
              </Typography.Title>
              <Typography.Text type="secondary">
                Browse folders in a tile view. Click folders to open them and files to select them.
              </Typography.Text>
            </Space>
          </Space>

          {value ? (
            <Tag
              title={value}
              style={{ maxWidth: '100%', marginInlineEnd: 0, fontFamily: 'monospace' }}
              color="default"
            >
              {value}
            </Tag>
          ) : (
            <Typography.Text italic type="secondary">
              No file selected
            </Typography.Text>
          )}
        </Space>

        <Space direction="vertical" size={20} style={{ width: '100%' }}>
          <Card
            size="small"
            style={{ borderRadius: 20, background: 'rgba(255,255,255,0.92)', borderColor: '#E8E8E8' }}
            styles={{ body: { padding: 16 } }}
          >
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Typography.Text style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#6B7280' }}>
                Folder path
              </Typography.Text>
              <Input
                value={folderInput}
                disabled={disabled}
                onChange={(ev) => setFolderInput(ev.target.value)}
                onPressEnter={handleOpenFolder}
                placeholder="Server folder path (e.g. /home/you/Pegasus/test-data)"
                style={{ fontFamily: 'monospace', borderRadius: 12 }}
              />
              <Button
                type="primary"
                block
                disabled={disabled || loading}
                onClick={handleOpenFolder}
                icon={loading ? <LoadingOutlined /> : <FolderOpenOutlined />}
                style={{
                  borderRadius: 12,
                  background: '#EB4C4C',
                  boxShadow: '0 8px 18px rgba(235, 76, 76, 0.2)',
                }}
              >
                {loading ? 'Loading…' : 'Open folder'}
              </Button>

              {browseHint ? <Typography.Text type="secondary">{browseHint}</Typography.Text> : null}
              {error ? <Alert type="error" showIcon message="Error" description={error} /> : null}
            </Space>
          </Card>

          {hasListed ? (
            <Card
              size="small"
              style={{ borderRadius: 20, background: 'rgba(255,255,255,0.92)', borderColor: '#E8E8E8' }}
              styles={{ body: { padding: 16 } }}
            >
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Space wrap size={8} style={{ width: '100%', color: '#475569' }}>
                  <FolderOutlined style={{ color: '#94A3B8' }} />
                  <Typography.Text style={{ minWidth: 0, flex: 1, fontFamily: 'monospace', fontSize: 11 }} ellipsis={{ tooltip: listedDir ?? (loading ? 'Loading…' : '—') }}>
                    {listedDir ?? (loading ? 'Loading…' : '—')}
                  </Typography.Text>
                  <Tag>{entries.length} items</Tag>
                  {parentPath ? (
                    <Button
                      size="small"
                      disabled={disabled || loading}
                      onClick={handleGoUp}
                      icon={<ArrowUpOutlined />}
                    >
                      Up
                    </Button>
                  ) : null}
                </Space>

                {truncated ? (
                  <Alert
                    type="warning"
                    showIcon
                    message="Listing truncated - only the first 5000 entries are shown."
                  />
                ) : null}

                <div
                  style={{
                    maxHeight: '34rem',
                    overflowY: 'auto',
                    borderRadius: 20,
                    border: '1px solid #E8E8E8',
                    background: '#FCFCFC',
                    padding: 12,
                  }}
                >
                  {!loading && entries.length === 0 ? <Empty description="Empty folder" /> : null}

                  {loading && entries.length === 0 ? (
                    <div
                      style={{
                        minHeight: 208,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: 12,
                        border: '1px dashed #E2E8F0',
                        background: '#FFFFFF',
                        color: '#94A3B8',
                      }}
                    >
                      <Space>
                        <Spin indicator={<LoadingOutlined style={{ color: '#EB4C4C' }} />} />
                        <span>Loading…</span>
                      </Space>
                    </div>
                  ) : null}

                  {entries.length > 0 ? (
                    <List
                      grid={{ gutter: 16, xs: 1, sm: 2, md: 2, lg: 3, xl: 3, xxl: 4 }}
                      dataSource={entries}
                      renderItem={(e) => {
                        const selected = !e.is_dir && e.path === value
                        return (
                          <List.Item>
                            <Card
                              hoverable={!disabled}
                              onClick={() => {
                                if (!disabled) handleEntryClick(e)
                              }}
                              style={{
                                minHeight: 192,
                                borderRadius: 18,
                                textAlign: 'center',
                                borderColor: selected ? '#EB4C4C' : '#E8E8E8',
                                background: selected ? 'rgba(235, 76, 76, 0.08)' : '#FFFFFF',
                                boxShadow: selected ? '0 8px 20px rgba(235, 76, 76, 0.12)' : undefined,
                                cursor: disabled ? 'not-allowed' : 'pointer',
                              }}
                              styles={{
                                body: {
                                  minHeight: 192,
                                  padding: 16,
                                  display: 'flex',
                                  flexDirection: 'column',
                                  alignItems: 'center',
                                  justifyContent: 'flex-start',
                                  gap: 8,
                                },
                              }}
                            >
                              <div
                                style={{
                                  width: 96,
                                  height: 96,
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  borderRadius: 18,
                                  border: e.is_dir ? '1px solid #DBEAFE' : '1px solid #E2E8F0',
                                  background: e.is_dir ? '#EFF6FF' : '#F8FAFC',
                                  color: e.is_dir ? '#3B82F6' : '#64748B',
                                  transform: selected ? 'scale(1.03)' : 'none',
                                  transition: 'transform 0.2s ease',
                                }}
                              >
                                {e.is_dir ? <FolderOutlined style={{ fontSize: 48 }} /> : <FileOutlined style={{ fontSize: 48 }} />}
                              </div>

                              <Typography.Text
                                strong
                                title={e.name}
                                style={{
                                  width: '100%',
                                  whiteSpace: 'normal',
                                  wordBreak: 'break-word',
                                  fontFamily: 'monospace',
                                  color: selected ? '#111827' : '#374151',
                                }}
                              >
                                {e.name}
                              </Typography.Text>

                              <Typography.Text style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#94A3B8' }}>
                                {e.is_dir ? 'Folder' : 'File'}
                              </Typography.Text>

                              {selected ? <Tag color="red">Selected</Tag> : null}
                            </Card>
                          </List.Item>
                        )
                      }}
                    />
                  ) : null}
                </div>
              </Space>
            </Card>
          ) : null}
        </Space>
      </Space>
    </Card>
  )
}