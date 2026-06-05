/**
 * Live validation job status (queued / running / percent / queue position).
 */

function formatPercent(n) {
  if (!Number.isFinite(n)) return null
  return `${Math.max(0, Math.min(100, Number(n))).toFixed(1)}%`
}

export default function ValidationJobProgress({
  phase,
  jobId,
  message,
  progress = {},
  elapsedLabel,
  variant = 'default',
}) {
  const pct = formatPercent(progress.percent)
  const queuePos = progress.queue_position
  const pendingAhead = progress.pending_ahead
  const runningJobs = progress.running_jobs
  const maxConcurrency = progress.max_concurrency

  const isCompact = variant === 'compact'
  const wrapStyle = isCompact
    ? {
        marginBottom: 12,
        padding: '11px 14px',
        borderRadius: 9,
        background: 'var(--accent-muted)',
        border: '1px solid var(--accent-border)',
      }
    : {
        marginBottom: 16,
        padding: '14px 16px',
        borderRadius: 10,
        background: 'var(--surface-2)',
        border: '1px solid var(--border-1)',
      }

  const title =
    phase === 'queued' ? 'Queued — waiting for a worker slot'
      : phase === 'accepted' ? 'Job accepted — starting worker'
        : phase === 'uploading' || phase === 'upload' ? 'Uploading files'
          : phase === 'running' || phase === 'validating' ? 'Validation in progress'
            : 'Working…'

  return (
    <div style={wrapStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span
          style={{
            width: 14,
            height: 14,
            borderRadius: '50%',
            border: '2px solid var(--accent-border)',
            borderTopColor: 'var(--accent)',
            animation: 'spin 0.7s linear infinite',
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>{title}</span>
        {elapsedLabel ? (
          <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-3)', fontFamily: 'Geist Mono, monospace' }}>
            {elapsedLabel}
          </span>
        ) : null}
      </div>

      {message ? (
        <p style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--text-2)', lineHeight: 1.45 }}>{message}</p>
      ) : null}

      <div style={{ fontSize: 12, color: 'var(--text-3)', display: 'flex', flexWrap: 'wrap', gap: '8px 16px' }}>
        {jobId ? <span>Job <code style={{ fontSize: 11 }}>{jobId}</code></span> : null}
        {phase ? <span>Phase: <strong>{phase}</strong></span> : null}
        {pct ? <span>Progress: <strong>{pct}</strong></span> : null}
        {queuePos != null ? (
          <span>
            Queue position: <strong>{Number(queuePos) + 1}</strong>
            {pendingAhead != null ? ` (${pendingAhead} ahead)` : ''}
          </span>
        ) : null}
        {runningJobs != null && maxConcurrency != null ? (
          <span>Parallel: <strong>{runningJobs}</strong> / {maxConcurrency} slots</span>
        ) : null}
      </div>

      <p style={{ margin: '10px 0 0', fontSize: 12, color: 'var(--text-4)' }}>
        Large files (e.g. 100M rows) often take several minutes. Keep this tab open; if the backend crashes you will see a red banner at the top.
      </p>
    </div>
  )
}
