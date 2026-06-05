import { formatDelimiterForDisplay, isAutoDelimiter } from './delimiterDisplay'

/**
 * Shows the delimiter that will be used for validation (especially after auto-detect).
 */
export default function ResolvedDelimiterNotice({
  requestedDelimiter = 'auto',
  resolvedDelimiter = '',
  compact = false,
}) {
  const resolved = String(resolvedDelimiter || '').trim()
  const requested = String(requestedDelimiter || '').trim() || 'auto'
  const auto = isAutoDelimiter(requested)

  if (!resolved && auto) {
    return (
      <div style={{
        marginBottom: compact ? 10 : 12,
        padding: compact ? '8px 12px' : '10px 14px',
        borderRadius: 10,
        background: 'var(--surface-2)',
        border: '1px solid var(--border-1)',
        fontSize: 12,
        color: 'var(--text-3)',
      }}>
        Delimiter will be detected from your files when column preview loads.
      </div>
    )
  }

  if (!resolved) return null

  const showBoth = auto && resolved.toLowerCase() !== requested.toLowerCase()

  return (
    <div style={{
      marginBottom: compact ? 10 : 12,
      padding: compact ? '10px 12px' : '12px 14px',
      borderRadius: 10,
      background: 'var(--accent-muted)',
      border: '1px solid var(--accent-border)',
    }}>
      <div style={{
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: 'var(--accent)',
        marginBottom: 6,
      }}>
        Delimiter for validation
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-1)', lineHeight: 1.45 }}>
        {showBoth ? (
          <>
            Requested <code style={{ fontFamily: 'Geist Mono, monospace', fontSize: 12 }}>{requested}</code>
            {' → '}
            resolved to{' '}
            <strong style={{ fontFamily: 'Geist Mono, monospace', fontSize: 13 }}>
              {formatDelimiterForDisplay(resolved)}
            </strong>
          </>
        ) : (
          <>
            Using{' '}
            <strong style={{ fontFamily: 'Geist Mono, monospace', fontSize: 13 }}>
              {formatDelimiterForDisplay(resolved)}
            </strong>
          </>
        )}
      </div>
      <p style={{ fontSize: 11, color: 'var(--text-3)', margin: '8px 0 0', lineHeight: 1.4 }}>
        Confirm this matches how your files are split before running validation. Change the delimiter below if the preview columns look wrong.
      </p>
    </div>
  )
}
